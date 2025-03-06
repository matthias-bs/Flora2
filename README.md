# Flora2
**ESP32/MicroPython Irrigation System**

**flora2** is a derivative of [**flora1**](https://github.com/matthias-bs/Flora1).

![flora2](https://user-images.githubusercontent.com/83612361/236630700-53796c17-c603-4072-bc65-ac93b352fe89.jpg)


## Features
* Running on Espressif ESP32 Microcontroller ([HiLetgo ESP-WROOM-32 ESP32 ESP-32S Development Board](http://www.hiletgo.com/ProductDetail/1906566.html))<br>
  (Compatibility to Raspberry Pi was planned, but is currently broken.) 
* Software coded in [MicroPython](https://micropython.org/), must be copiled to bytecode [(__*.mpy__)](https://docs.micropython.org/en/latest/reference/glossary.html#term-.mpy-file) for ESP32
* Plant status monitorig
    * via Xiaomi Mi Flora Plant Sensors (Bluetooth Low Energy)
    * via capacitive Soil Moisture Sensors (wired)
* Tank low / Tank empty Status Monitoring with XKC-Y25-T12V (Non-Contact Liquid Level Sensor)
* Temperature Sensor [DS18B20](https://www.maximintegrated.com/en/products/sensors/DS18B20.html) (optional)
* Weather (i.e. Temperature, Barometric Pressure and Humidity) Sensors
    * [BME280](https://www.bosch-sensortec.com/products/environmental-sensors/humidity-sensors-bme280/) (optional)
    * [M5Stack ENV III](http://docs.m5stack.com/en/hat/hat_envIII)
* Pump Control (5 or 12 Volts) with [Infineon BTS117](https://www.infineon.com/cms/en/product/power/smart-low-side-high-side-switches/low-side-switches/classic-hitfet-24v/bts117/) _N channel vertical power FET in Smart SIPMOS® technology_
* Automatic and manual Irrigation Control with one or two Pumps
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
