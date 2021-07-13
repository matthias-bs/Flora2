###############################################################################
# moisture.py
#
# This module provides the Moisture class
#
# - provides analog moisture sensor value
#  
#
# created: 03/2021 updated: 06/2021
#
# This program is Copyright (C) 03/2021 Matthias Prinke
# <m.prinke@arcor.de> and covered by GNU's GPL.
# In particular, this program is free software and comes WITHOUT
# ANY WARRANTY.
#
# History:
#
# 20210317 Created
# 20210521 Modified return value in case of invalid data
# 20210622 Changed to use adc1_cal and 6dB attenuation
#
# ToDo:
# - 
#
###############################################################################

import sys
import config as cfg

if sys.platform == "esp32":
    import adc1_cal
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
        _x1 (int):      Sensor output for 100% moisture [mV]
        _x2 (int):      Sensor output for   0% moisture [mV]
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
        self.raw    = 0
        
        if sys.implementation.name == "micropython" and sys.platform == "esp32":
            self._adc = adc1_cal.ADC1Cal(Pin(self._pin), cfg.MOIST_DIV)
                        
            # set 6dB input attenuation ("suggested voltage range": 150 - 1750mV)
            self._adc.atten(ADC.ATTN_6DB)
            
            # set 9 bit return values (returned range 0-511)
            self._adc.width(ADC.WIDTH_9BIT)   

        

    @property
    def moisture(self):
        """
        Get analog moisture sensor measurement value [%].

        Returns:
            bool, int: valid flag, moisture [%]
        """
        if sys.platform == "esp32":
            raw_val = self._adc.voltage
            self.raw = raw_val
            valid = True if (raw_val >= self._ul and raw_val <= self._oh) else False
            moisture = int(self._m * (raw_val - self._x1) + self._y1)
            moisture = moisture if valid else raw_val
            return (valid, moisture)
        else:
            # dummy value indicating invalid data
            return (False, -1)

    
#    def __str__(self):
#        if (self.name != ""):
#            name_str = "Name: {} ".format(self.name)
#        else:
#            name_str = ""
#        if (sys.platform == "esp32"):
#            raw_val = self._adc.read()
#        else:
#            raw_val = -1
#        valid, moisture = self.moisture
#        return ("{}Pin# {:2}, Pin# empty: {:2}, raw value: {}, value: {}"
#                .format(name_str, self._pin, raw_val, moisture))
#
