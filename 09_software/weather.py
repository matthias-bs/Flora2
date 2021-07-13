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
#
# ToDo:
# - 
#
###############################################################################

import config as cfg
from print_line import *

from machine import Pin
from machine import I2C, SoftI2C
import bme280

def weather_data():
    valid = True
    
    try:
        bus = SoftI2C(scl=Pin(cfg.GPIO_I2C_SCL), sda=Pin(cfg.GPIO_I2C_SDA))
    except OSError as exc:
        valid = False
        print_line('I2C Bus Error! ({})!'.format(exc.args[1]), error=True, console=True, sd_notify=True)
    
    try:
        bme = bme280.BME280(i2c=bus, address=cfg.BME280_ADDR, mode=bme280.BME280_OSAMPLE_1)
    except OSError as exc:
        valid = False
        print_line('Failed to access BME280 sensor at I2C address {}!'.format(hex(cfg.BME280_ADDR)), 
                    error=True, console=True, sd_notify=True)

    data = {}
    if valid:
        data['temperature'] = round(bme.temperature(), 1)
        data['pressure']    = round(bme.pressure(), 0)
        data['humidity']    = round(bme.humidity(), 0)
    
    return (valid, data)
