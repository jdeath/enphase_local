"""Support for Enphase-local Monitoring API."""
from __future__ import annotations

from contextlib import suppress
from copy import copy
from dataclasses import dataclass
from datetime import timedelta
import logging
import statistics

import json
import requests

from requests.exceptions import ConnectTimeout, HTTPError
import voluptuous as vol
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import Throttle
from urllib3.exceptions import InsecureRequestWarning

_LOGGER = logging.getLogger(__name__)

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    CONF_IP_ADDRESS,
    CONF_NAME,
    CONF_API_KEY,
    CONF_USERNAME,
    CONF_PASSWORD,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfTemperature,
    ENERGY_WATT_HOUR,
    POWER_WATT,
    Platform,
    PERCENTAGE
)

USE_INVERTERS = "use_inverters"
USE_CLOUD = "use_cloud"
CONF_SERIAL = "serial"
CONF_SITEID = "siteid"

DOMAIN = "enphase_local"

UPDATE_DELAY = timedelta(seconds=15)
UPDATE_DELAY_INVERTER = timedelta(seconds=60)
UPDATE_DELAY_CLOUD = timedelta(seconds=600)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_IP_ADDRESS, default="envoy.local"): cv.string,
        vol.Optional(CONF_NAME, default="EnphaseLocal"): cv.string,
        vol.Optional(USE_INVERTERS, default="False"): cv.boolean,
        
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_SERIAL): cv.string,
        vol.Required(CONF_SITEID): cv.string,
    }
)


@dataclass
class EnphaseLocalSensorEntityDescription(SensorEntityDescription):
    """Describes Enphase-local sensor entity."""

    extra_attribute: str | None = None


SENSOR_TYPES_LOCAL: tuple[EnphaseLocalSensorEntityDescription, ...] = (
    EnphaseLocalSensorEntityDescription(
        key="powerProduction",
        name="Power Production",
        native_unit_of_measurement=POWER_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:current-ac",
    ),
    EnphaseLocalSensorEntityDescription(
        key="powerConsumption",
        name="Power Consumption",
        native_unit_of_measurement=POWER_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:current-ac",
    ),
    EnphaseLocalSensorEntityDescription(
        key="powerNet",
        name="Power Net",
        native_unit_of_measurement=POWER_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:current-ac",
    ),
    EnphaseLocalSensorEntityDescription(
        key="powerExport",
        name="Power Export",
        native_unit_of_measurement=POWER_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:current-ac",
    ),
    EnphaseLocalSensorEntityDescription(
        key="powerImport",
        name="Power Import",
        native_unit_of_measurement=POWER_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:current-ac",
    ),
    EnphaseLocalSensorEntityDescription(
        key="energyProdLifetime",
        name="Energy Production Lifetime",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:current-ac",
    ),
    EnphaseLocalSensorEntityDescription(
        key="energyConLifetime",
        name="Energy Consumption Lifetime",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:current-ac",
    ),
    EnphaseLocalSensorEntityDescription(
        key="energyNetLifetime",
        name="Energy Net Lifetime",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:current-ac",
    ),     
)

SENSOR_TYPES_CLOUD: tuple[EnphaseLocalSensorEntityDescription, ...] = (
    EnphaseLocalSensorEntityDescription(
        key="energyExport",
        name="Energy Export",
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        icon="mdi:solar-power",
    ),
    EnphaseLocalSensorEntityDescription(
        key="energyNet",
        name="Net Export Energy",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:solar-power",
    ),
    EnphaseLocalSensorEntityDescription(
        key="energyImport",
        name="Energy Import",
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        icon="mdi:solar-power",
    ),
    EnphaseLocalSensorEntityDescription(
        key="energyProduction",
        name="Energy Production",
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        icon="mdi:solar-power",
    ),
    EnphaseLocalSensorEntityDescription(
        key="energyConsumption",
        name="Energy Consumption",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:solar-power",
    ),  
)

def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Create the Enphase Monitoring API sensor."""
    
    platform_name = config[CONF_NAME]
    ipaddress = config[CONF_IP_ADDRESS]
    useInverters = config[USE_INVERTERS]
    userName = config[CONF_USERNAME]
    password = config[CONF_PASSWORD]
    serialNumber = config[CONF_SERIAL]
    siteID = config[CONF_SITEID]
    
    # Get 12-month Token for local access
    postData = {'user[email]': userName, 'user[password]': password}
    response = requests.post('https://enlighten.enphaseenergy.com/login/login.json?',data=postData)
    response_data = response.json()
    postData = {'session_id': response_data['session_id'], 'serial_num': serialNumber, 'username':userName}
    response = requests.post('https://entrez.enphaseenergy.com/tokens', json=postData)
    token = response.text
    
    headers = {'Authorization': "Bearer {}".format(token)}
    
    data = EnphaseData(hass, headers,ipaddress)
    
    # Create entities
    entities = [
        EnphaseSensor(platform_name, data, description)
        for description in SENSOR_TYPES_LOCAL
    ]

    
    cloudData = EnphaseDataCloud(hass, userName, password, siteID) 
    for description in SENSOR_TYPES_CLOUD:
        entities.append( EnphaseSensor(platform_name, cloudData, description) )
    
    if useInverters:
        inverterData = EnphaseDataInverters(hass,headers,ipaddress)
    
        session = requests.Session()
        session.verify = False
        
        auth_response = session.get('https://' + ipaddress + '/api/v1/production/inverters', headers=headers)
        if auth_response.ok:    
            value_json = auth_response.json()
            for x in value_json:
                sensorName = "inverter_" + str(x.get("serialNumber"))
                description = EnphaseLocalSensorEntityDescription(key=sensorName,name=sensorName,native_unit_of_measurement=UnitOfPower.WATT,device_class=SensorDeviceClass.POWER,)
                entities.append(EnphaseSensor(platform_name, inverterData, description))
    
    add_entities(entities, True)
    

class EnphaseSensor(SensorEntity):
    """Representation of an Enphase Monitoring API sensor."""

    entity_description: EnphaseLocalSensorEntityDescription

    def __init__(
        self,
        platform_name,
        data,
        description: EnphaseLocalSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        self.entity_description = description
        self._platform_name = platform_name
        self._data = data
        self._attr_name = f"{platform_name}_{description.name}"

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        if extra_attr := self.entity_description.extra_attribute:
            try:
                return {extra_attr: self._data.info.get(self.entity_description.key)}
            except KeyError:
                pass
        return None
    
    @property
    def unique_id(self) -> str:
        """Return a unique, Home Assistant friendly identifier for this entity."""
        return self._attr_name
           
    def update(self) -> None:
        """Get the latest data from the sensor and update the state."""
        self._data.update()
        self._attr_native_value = self._data.data.get(self.entity_description.key)

class EnphaseDataCloud:
    """Get and update the latest data."""

    def __init__(self, hass, userName, password, siteID):
        """Initialize the data object."""
        self.hass = hass
        self.userName = userName
        self.password = password
        self.siteID = siteID
        self.data = {}
        self.session = requests.Session()
        self.token = ''
        self.url = "https://enlighten.enphaseenergy.com/pv/systems/" + self.siteID + "/today"
        self.login()
        
    def login(self):
        auth_data = {        
        'user[email]':     self.userName,
        'user[password]':  self.password,
        }
        self.session.post("https://enlighten.enphaseenergy.com/login/login.json",data=auth_data)
        
        
    @Throttle(UPDATE_DELAY_CLOUD)
    def update(self):
        """Update the data from the Enphase Monitoring API."""
        
        auth_response = self.session.get(self.url); 
        if auth_response.ok:
            responseJSON = auth_response.json()
            
            if responseJSON["stats"][0] is not None:
                dailyTotal = responseJSON["stats"][0]["totals"]
            else:
                dailyTotal = None
            
            #_LOGGER.debug(dailyTotal)
            production = 0
            consumption = 0
            grid_home = 0
            solar_grid = 0
            
            if "production" in dailyTotal:
                production = dailyTotal["production"]
            self.data["energyProduction"] = production
                
            if "consumption" in dailyTotal:    
                consumption = dailyTotal["consumption"]
            self.data["energyConsumption"] = consumption
            
            if "grid_home" in dailyTotal:
                grid_home = dailyTotal["grid_home"]
            self.data["energyImport"] = grid_home
            
            if "solar_grid" in dailyTotal:
                solar_grid = dailyTotal["solar_grid"]
            self.data["energyExport"] = solar_grid
                 
            # Get Net Energy from cloud to be consistent
            self.data["energyNet"] = production - consumption
            
            
            
            
class EnphaseData:
    """Get and update the latest data."""

    def __init__(self, hass, headers, ipaddress):
        """Initialize the data object."""
        self.hass = hass
        self.headers = headers
        self.ipaddress = ipaddress
        self.data = {}
        
    @Throttle(UPDATE_DELAY)
    def update(self):
        """Update the data from the Enphase Monitoring API."""
        
        session = requests.Session()
        session.verify = False
        
        auth_response = session.get('https://' + self.ipaddress + '/ivp/meters/readings', headers=self.headers)
        if auth_response.ok:
            value_json = auth_response.json()
            powerProduction = value_json[0].get("activePower")
            self.data["powerProduction"] = powerProduction
            powerConsumption = value_json[1].get("activePower")
            self.data["powerConsumption"]= powerConsumption
            self.data["powerNet"] = powerProduction-powerConsumption
            self.data["powerExport"] = max(0,powerProduction - powerConsumption)
            self.data["powerImport"] = max(0,powerConsumption - powerProduction)
            
            energyProductionLifetime = value_json[0].get("actEnergyDlvd")
            self.data["energyProdLifetime"] = energyProductionLifetime
            energyConsumptionLifetime = value_json[1].get("actEnergyDlvd")
            self.data["energyConLifetime"] = energyConsumptionLifetime
            self.data["energyNetLifetime"] = energyProductionLifetime - energyConsumptionLifetime

class EnphaseDataInverters:
    """Get and update the latest data."""

    def __init__(self, hass, headers,ipaddress):
        """Initialize the data object."""
        self.hass = hass
        self.headers = headers
        self.ipaddress = ipaddress
        self.data = {}
        
    @Throttle(UPDATE_DELAY_INVERTER)
    def update(self):
        """Update the data from the Enphase Monitoring API."""
        session = requests.Session()
        session.verify = False
        auth_response = session.get('https://' + self.ipaddress + '/api/v1/production/inverters', headers=self.headers)
        if auth_response.ok:
            value_json = auth_response.json()
            for x in value_json:
                sensorName = "inverter_" + str(x.get("serialNumber"))
                self.data[sensorName] = x.get("lastReportWatts")            
