# enphase_local
"Local" Integration for Enphase Envoy Firmware 7.3+
Uses endpoints found by @del13r on this thread: https://community.home-assistant.io/t/enphase-envoy-d7-firmware-with-jwt-a-different-approach/594082

# Target Audiance
This integration is for those with Enphase Envoy Firmware 7.3+ who is setup in “load only” or "total-consumption" mode. This means your envoy does not natively return the total imported/exported energy. It returns the power, but does not integrate it. One option is to use a Reiman Sum Integral to integrate the power. Instead, this integration gets the energy information from enphase cloud. Not sure how the cloud knows, but the local envoy does not. I find it to be reasonably accurate (I can read my actual production and net energy meter with a SDR).

Currently, this works for “load only” or "total-consumption" . Perhaps I will add ability for other setups

Despite the name, this integration gets both local and cloud data. It started out at getting local data, but not all the required data was local.

Local Data From your envoy: Current production,consumption,import,export power . Inverter power production

Cloud Data: Energy Production, Consumption, Import, Export, Net

# Installation
1. Add this repo into hacs
1. Download enphase_local integration
1. Add the following yaml to your homeassistant configuration.yaml under the ```sensor:``` key

```
- platform: enphase_local
  ip_address: 192.168.1.XXX # Optional, if not entered, will default to envoy.local
  use_inverters: true # Optional, if false or not added it will not provide inverter data
  username: 'user@email.com'  # Required, your enphase username/email - Used to get local token and cloud data
  password: 'Password123' # Required, your enphase password - Used to get local token and cloud data
  siteid: 'XXXXXX' # Required, your enphasse site_id. You can find this in the enphase app - Used to get cloud data
  serial: 'XXXX' # Requried, your envoy serial number. Find this going to envoy.local - Used to get cloud data
```   
You will get self explanitory sensors called:
sensor.enphaselocal_X_Y 
where X is: production, consumption, export, import, net (production - consumption)
where Y is power, energy

If use inverters, will get power production of each inverter
sensor.enphaselocal_inverter_XXXX where XXXX is the interver serial

In sensor.py you can change how often it queries local power, intervers, and the cloud seperately. Defaults to 15 seconds, 60 seconds, and 10 minutes respectively.
# To Do
1. Cache Local Token Between Homeassistant Restarts incase cloud is down
1. Have a version that switched for people with "Load with Solar Production". This can be queried from local envoy, so should be easy
