###############################################################################
# moisture.py
#
# This module provides the Moisture class
#
# - provides analog moisture sensor value
#  
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
# 20210317 Created
#
# ToDo:
# - 
#
###############################################################################

import sys
from gpio import *

if sys.platform == "esp32":
    from machine import Pin
    from machine import ADC

###############################################################################
# Moisture class - Moisture sensor values
###############################################################################
class Moisture:
    """
    Get moisture sensor value.

    Attributes:
        name (string):  instance name (for debugging)
        _y1 (int):      maximum moisture [%]
        _y2 (int):      minimum moisture [%]
        _x1 (int):      ADC output for 100% moisture [n]
        _x2 (int):      ADC output for   0% moisture [n]
        _m  (float):    ADC value to percentage transfer function - slope
        _ul (int):      lower limit for ADC value
        _oh (int):      upper limit for ADC value
    """
    def __init__(self, pin_no, min_val, max_val, name=""):
        """
        The constructor for Moisture class.

        Parameters:
            pin_no (int):           input pin no. for analog moisture sensor
            min_val (int):          minimum moisture (  0 %) ADC reading
            max_val (int):          maximum moisture (100 %) ADC reading
            name (string):          instance name
        """
        self.name = name
        self._pin   = pin_no
        self._y1    = 100
        self._y2    = 0
        self._x1    = max_val
        self._x2    = min_val
        self._m     = (self._y2 - self._y1) / (self._x2 - self._x1)
        self._ul    = min_val if (min_val < max_val) else max_val
        self._oh    = max_val if (max_val > min_val) else min_val
        
        if sys.implementation.name == "micropython" and sys.platform == "esp32":
            # create ADC object on GPIO pin
            self._adc = ADC(Pin(self._pin, Pin.IN))
            
            # set 11dB input attenuation (voltage range roughly 0.0v - 3.6v)
            self._adc.atten(ADC.ATTN_11DB)
            
            # set 9 bit return values (returned range 0-511)
            self._adc.width(ADC.WIDTH_9BIT)   

        

    @property
    def moisture(self):
        """
        Get analog moisture sensor measurement value [%].

        Returns:
            bool, int: valid flag, moisture [%]
        """
        if sys.implementation.name == "micropython" and sys.platform == "esp32":
            raw_val = self._adc.read()
            valid = True if (raw_val >= self._ul and raw_val <= self._oh) else False
            moisture = int(self._m * (self._adc.read() - self._x1) + self._y1)
            return valid, moisture if (valid) else raw_val
        else:
            # dummy value indicating invalid data
            return (False, -1)

    
    def __str__(self):
        if (self.name != ""):
            name_str = "Name: {} ".format(self.name)
        else:
            name_str = ""
        if (sys.platform == "esp32"):
            raw_val = self._adc.read()
        else:
            raw_val = -1
        valid, moisture = self.moisture
        return ("{}Pin# {:2}, Pin# empty: {:2}, raw value: {}, value: {}"
                .format(name_str, self._pin, raw_val, moisture))
