# enphase_local
"Local" Integration for Enphase Envoy Firmware 7.3+

# Target Audiance
This integration is for those with Enphase Envoy Firmware 7.3+ who is setup in “load only” or "total-consumption" mode. This means your envoy does not natively return the total imported/exported energy. It returns the power, but does not integrate it. One option is to use a Reiman Sum Integral to integrate the power. This integration gets the information from enphase cloud. Not sure how the cloud knows, but the local envoy does not, but I find it more accurate.

Currently, this works for “load only” or "total-consumption" . Perhaps I will add ability for other setups

This integration gets both local and cloud data.

Local Data From your envoy: Current import/export power . Inverter production data

Cloud Data: Energy Production,Consumption, Import, Export




