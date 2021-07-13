###############################################################################
# temperature.py
#
# This module provides the Temperature class
#
# - provides DS18x20 OneWire temperature sensor value
# - suppports multiple sensors
# - restricted to MicroPython
#
# created: 03/2021 updated: 05/2021
#
# This program is Copyright (C) 03/2021 Matthias Prinke
# <m.prinke@arcor.de> and covered by GNU's GPL.
# In particular, this program is free software and comes WITHOUT
# ANY WARRANTY.
#
# History:
#
# 20210317 Created
# 20210520 Improved robustness
#          Changed code to assume MicroPython/ESP32
#          Corrected comments/description
# 20210521 Modified index handling
#
# ToDo:
# - for multiple sensors: is the list returned by scan() ordered?
#
###############################################################################

import onewire
import ds18x20
import time
import binascii
from machine import Pin
from gpio import *

###############################################################################
# Temperature class - Temperature sensor values
###############################################################################
class Temperature:
    """
    Get Temperature sensor value.

    Attributes:
        name (string):  instance name (for debugging)
        devices (int):  number of DS18x20 devices found
    """
    def __init__(self, pin_no, name=""):
        """
        The constructor for Temperature class.

        Parameters:
            pin_no (int):           input pin no. for analog moisture sensor
            name (string):          instance name
        """
        self.name    = name
        self.devices = 0
        self._pin    = pin_no
        try:
            self._ds_sensor = ds18x20.DS18X20(onewire.OneWire(Pin(self._pin)))
        except:
            print('Error: Temperature(): sensor access failed')
            
        self._roms = self._ds_sensor.scan()
        self.devices = len(self._roms)

    def show_devices(self):
        for i, dev in enumerate(self._roms):
            print('{}: {}'.format(i, binascii.hexlify(dev)))
    
    def temperature(self, sensor_index=0):
        """
        Get digital temperature sensor value [°C].

        Temperature is read from DS18x20 sensor via one-wire interface 

        Parameters:
            sensor_index (int): index into array of sensors
        
        Returns:
            float: temperature [°C]
        """
        if (sensor_index > self.devices-1):
            print('Error: Temperature(): sensor index out of range')
            return None
        
        self._ds_sensor.convert_temp()
        time.sleep_ms(750)
        return (self._ds_sensor.read_temp(self._roms[sensor_index]))
            
    
#    def __str__(self):
#        if (self.name != ""):
#            name_str = "Name: {} ".format(self.name)
#        else:
#            name_str = ""
#        return ("{}Pin# {:2}, devices: {:2}, value: {}"
#                .format(name_str, self._pin, self.devices, self.temperature))
#
