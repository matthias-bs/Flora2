###############################################################################
# sensor_power.py
#
# This module provides the Sensor_Power class
#
# - controls the sensor power via GPIO
#
# created: 03/2021 updated: 03/2021
#
# This program is Copyright (C) 03/2021 Matthias Prinke
# <m.prinke@arcor.de> and covered by GNU's GPL.
# In particular, this program is free software and comes WITHOUT
# ANY WARRANTY.
#
# History:
#
# 20210316 Created
#
# ToDo:
# - 
#
###############################################################################

import sys
from time import sleep
from gpio import *

if sys.implementation.name == "micropython":
    from machine import Pin
    
###############################################################################
# SensorPower class - Sensor power control
###############################################################################
class SensorPower:
    """Control the sensor power.

    Attributes:
        p_power (int):          output pin no. for power control
        name (string):          instance name (for debugging)
    """
    def __init__(self, pin_sensor_power, name=""):
        """
        The constructor for SensorPower class.

        Parameters:
            pin_pump_power (int):  GPIO pin for sensor power control.
            name (string):         instance name (for debugging)
        """
        self.p_power = pin_sensor_power
        if sys.implementation.name == "micropython" and sys.platform == "esp32":
            self.pin_power = Pin(self.p_power, Pin.OUT, value = 0)
        else:
            GPIO.setup(self.p_power, GPIO.OUT)
            GPIO.output(self.p_power, GPIO.LOW)
            
        self.name = name

    def enable(self, power):
        """
        Sensor power control.

        Parameters:
            power (bool): power on/off
        """
        self.status = power
        if sys.implementation.name == "micropython" and sys.platform == "esp32":
            self.pin_power.value(power)
        else:
            GPIO.output(self.p_power, power)

    def __str__(self):
        return ("{}Pin# driver control: {:2}, Pin# driver status: {:2}, Status: {:>10}"
                .format((self.name + ' ') if (self.name != '') else '', self.p_power, self.status))
