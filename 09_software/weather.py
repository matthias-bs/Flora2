###############################################################################
# weather.py
#
# This module provides weather sensor data
#
# - provides temperature, humidity and barometric pressure
#   from BME280 sensor connected to I2C bus interface
#  
#
# created: 05/2021 updated: 05/2021
#
# This program is Copyright (C) 05/2021 Matthias Prinke
# <m.prinke@arcor.de> and covered by GNU's GPL.
# In particular, this program is free software and comes WITHOUT
# ANY WARRANTY.
#
# History:
#
# 20210521 Created
# 20250305 Added M5Stack ENV III sensor
#          (http://docs.m5stack.com/en/hat/hat_envIII)
#
# ToDo:
# - 
#
###############################################################################

import config as cfg
from print_line import *

from machine import Pin
from machine import SoftI2C
import bme280
import sht30 # https://github.com/cdrajb/M5_ENVIII
import qmp6988 # https://github.com/cdrajb/M5_ENVIII

def weather_data():
    data = {}
    valid = False
    
    try:
        bus = SoftI2C(scl=Pin(cfg.GPIO_I2C_SCL), sda=Pin(cfg.GPIO_I2C_SDA))
    except OSError as exc:
        valid = False
        print_line(f'I2C Bus Error! ({exc.args[1]})!', error=True, console=True, sd_notify=True)
    
    try:
        bme = bme280.BME280(i2c=bus, address=cfg.BME280_ADDR, mode=bme280.BME280_OSAMPLE_1)
    except OSError as exc:
        print_line(f'Failed to access BME280 sensor at I2C address {hex(cfg.BME280_ADDR)}!', 
                   error=True, console=True, sd_notify=True)
    else:
        valid = True
        data['temperature'] = round(bme.temperature(), 1)
        data['pressure']    = round(bme.pressure(), 0)
        data['humidity']    = round(bme.humidity(), 0)

    try:
        sht = sht30.SHT30(i2c=bus)
    except OSError as exc:
        print_line(f'Failed to access M5Stack ENV III SHT30 sensor!',
                   error=True, console=True, sd_notify=True)
    else:
        valid = True
        temperature, humidity = sht.measure()
        data['temperature'] = round(temperature, 1)
        data['humidity']    = round(humidity, 0)
        
    try:
        qmp = qmp6988.QMP6988(i2c=bus)
    except OSError as exc:
        valid = False
        print_line(f'Failed to access M5Stack ENV III QMP6988 sensor!',
                   error=True, console=True, sd_notify=True)
    else:
        valid = True
        _, pressure = qmp.measure()
        data['pressure']    = round(pressure / 100.0, 0)

    return (valid, data)
