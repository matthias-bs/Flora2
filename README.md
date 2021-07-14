# Flora2
**ESP32/MicroPython Irrigation System**

**flora2** is a derivative of [**flora1**](https://github.com/matthias-bs/Flora1).

[Image]


## Features
* Plant status monitorig
    * via Xiaomi Mi Flora Plant Sensors (Bluetooth Low Energy)
    * via capacitive soil moisture sensors (wired)
* Tank low / tank empty status monitoring with XKC-Y25-T12V (Non-Contact Liquid Level Sensor)
* Temperature sensor [DS18B20](https://www.maximintegrated.com/en/products/sensors/DS18B20.html) (optional)
* Weather (i.e. Temperature, Barometric Pressure and Humidity) Sensor [BME280](https://www.bosch-sensortec.com/products/environmental-sensors/humidity-sensors-bme280/) (optional)
* Pump Control (5 or 12 Volts) with [Infineon BTS117](https://www.infineon.com/cms/en/product/power/smart-low-side-high-side-switches/low-side-switches/classic-hitfet-24v/bts117/) _N channel vertical power FET in Smart SIPMOS® technology_
* Automatic and manual Irrigation Control with one or two Pumps
* Status Reports via Email (HTML) with complex Trigger Filtering (limited Availability due to Memory Restrictions)
* Power Supply from [Solar Power Manager](https://www.waveshare.com/wiki/Solar_Power_Manager) with Lithium-Ion Battery and [6 V/5 W Solar Panel](https://www.waveshare.com/Solar-Panel-6V-5W.htm) (optional)
* Battery Voltage Monitoring (optional)
* Controlling and Monitoring via MQTT over WiFi

## Dashboard with [IoT MQTT Panel](https://snrlab.in/iot/iot-mqtt-panel-user-guide) (Example)

![IoTMQTTPanel_flora2o_s](https://user-images.githubusercontent.com/83612361/125654145-21e2d790-d30e-4eed-98f8-6d1096079c67.png)

----

## Disclaimer and Legal

> *Xiaomi* and *Mi Flora* are registered trademarks of *BEIJING XIAOMI TECHNOLOGY CO., LTD.*
>
> This project is a community project not for commercial use.
> The authors will not be held responsible in the event of device failure or withered plants.
>
> This project is in no way affiliated with, authorized, maintained, sponsored or endorsed by *Xiaomi* or any of its affiliates or subsidiaries.
