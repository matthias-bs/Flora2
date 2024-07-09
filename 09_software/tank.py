###############################################################################
# tank.py
#
# This module provides the Tank class
#
# - provides the tank fill level status values <low> and <empty>
#   by reading the according sensor outputs via GPIO pins
#
# created: 01/2021 updated: 02/2021
#
# This program is Copyright (C) 01/2021 Matthias Prinke
# <m.prinke@arcor.de> and covered by GNU's GPL.
# In particular, this program is free software and comes WITHOUT
# ANY WARRANTY.
#
# History:
#
# 20210117 Extracted from flora.py
# 20210201 Modified for compatibility with MicroPython / ESP32
# 20210211 Fixed low()/empty() on ESP32
# 20210519 Added global variable <tank>
#
# ToDo:
# - 
#
###############################################################################

import sys
from gpio import *

if sys.implementation.name == "micropython":
    from machine import Pin

##############################################################################
# Global variables
##############################################################################
tank = None

###############################################################################
# Tank class - Fill level sensor status
###############################################################################
class Tank:
    """
    Get the tank level sensor values of the low- and empty-mark.

    Attributes:
        name (string):  instance name (for debugging)
        low (bool):     fill-level low
        empty (bool):   fill-level empty
        p_low (int):    input pin no. for fill-level empty sensor
        p_empty (int):  input pin no. for fill-level low sensor 
    """
    def __init__(self, pin_sensor_low, pin_sensor_empty, name=""):
        """
        The constructor for Tank class.

        Parameters:
            pin_sensor_low (int):   GPIO pin no. of low level sensor.
            pin_sensor_empty (int): GPIO pin no. of empty level sensor.
            name (string):          instance name
        """
        self.name = name
        self.p_low = pin_sensor_low
        self.p_empty = pin_sensor_empty
        
        if sys.implementation.name == "micropython" and sys.platform == "esp32":
            self.pin_low = Pin(pin_sensor_low, Pin.IN)
            self.pin_empty = Pin(pin_sensor_empty, Pin.IN)
        else:
            GPIO.setup(self.p_low, GPIO.IN)
            GPIO.setup(self.p_empty, GPIO.IN)

    @property
    def empty(self):
        """
        Get current status of tank empty level sensor.

        Returns:
            bool: True if tank is empty, false otherwise.
        """
        if sys.implementation.name == "micropython" and sys.platform == "esp32":
            return (self.pin_empty.value() == 1)
        else:
            return (GPIO.input(self.p_empty) == True)

    @property
    def low(self):
        """
        Get current status of tank low level sensor.

        Returns:
            bool: True if tank is low, false otherwise.
        """
        if sys.implementation.name == "micropython" and sys.platform == "esp32":
            return (self.pin_low.value() == 1)
        else:
            return (GPIO.input(self.p_low) == True)
    
    @property
    def status(self):
        """
        Get current status of tank level.

        Returns:
            int: 0 - empty, 1 - low, 2 - o.k.
        """
        if self.empty:
            return 0
        elif self.low:
            return 1
        else:
            return 2

#    def __str__(self):
#        if (self.name != ""):
#            name_str = "Name: {} ".format(self.name)
#        else:
#            name_str = ""
#        return ("{}Pin# low: {:2}, Pin# empty: {:2}, Low: {}, Empty: {}"
#                .format(name_str, self.p_low, self.p_empty, self.low, self.empty))
#
