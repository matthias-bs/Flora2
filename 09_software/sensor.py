###############################################################################
# sensor.py
#
# This module provides the Sensor class
#
# - stores sensor data
# - stores plant data (i.e. limits for environmental conditions)
# - compares sensor data with plant data
# - allows to check low battery, sensor data timeout and sensor data valid
#
# created: 01/2021 updated: 05/2021
#
# This program is Copyright (C) 01/2021 Matthias Prinke
# <m.prinke@arcor.de> and covered by GNU's GPL.
# In particular, this program is free software and comes WITHOUT
# ANY WARRANTY.
#
# History:
#
# 20210117 Extracted from flora.py
# 20210318 Added update_moisture_sensor() and update_temperature_sensor()
# 20210508 Added data()
#
# ToDo:
# - 
#
###############################################################################

from time import time
import json

##############################################################################
# Global variables
##############################################################################
sensors = None


###############################################################################
# Sensor class - Sensor and plant data and methods
###############################################################################
class Sensor:
    """
    This is a class for sensor data, plant specific limits and all the rest.
    
    Attributes:
        General:
        --------
        name (string):      sensor name
        tstamp (float):     timestamp of last sensor data reception
        plant (string):     name of the plant assigned to this sensor
        batt_min (int):     minimum battery level [%]
        _tout (float):      max. time between data updates
        valid (bool):       sensor data is valid
    
        Actual sensor values:
        ---------------------
        temp (float):       temperature [°C]
        cond (int):         conductivity [µS/cm]
        moist (int):        moisture [%]
        light (int):        light [lux]
        batt (int):         battery [%]
        
        Lower limits (desired by the plant):
        ------------------------------------
        temp_min (float):   temperature [°C]
        cond_min (int):     conductivity [µS/cm]
        moist_lo (int):     moisture (inner limit) [%] 
        moist_min (int):    moisture (outer limit) [%]
        light_min (int):    light [lux]
               
        Upper limits (desired by the plant):
        ------------------------------------
        temp_max (float):   temperature [°C]
        cond_max (int):     conductivity [µS/cm]
        moist_hi (int):     moisture (inner limit) [%]
        moist_max (int):    moisture (outer limit) [%]
        light_max (int):    light [lux]
        light_irr (int):    light [lux], limit for irr_duration
    """
    def __init__(self, sensor_name, tout, batt_min):
        """
        The constructor for Sensor class.

        Parameters:
            sensor_name (string): Sensor name
            tout (float):         max. time between data updates
            batt_min (float):     low battery warning level [%]
        """
        # General
        self.name = sensor_name
        self.address = 0
        self.tstamp = 0
        self.plant = "<undefined>"
        self.batt_min = batt_min
        self._tout = tout
        # Actual sensor values
        self.temp = -273
        self.cond = -1
        self.moist = -1
        self.light = -1
        self.batt = 100
        # Lower limits
        self.temp_min = 0.0
        self.cond_min = 0
        self.moist_lo = 0
        self.moist_min = 0
        self.light_min = 0
        # Upper limits
        self.temp_max = 0.0
        self.cond_max = 0
        self.moist_hi = 0
        self.moist_max = 0
        self.light_max = 0
        # Comparison results
        self.batt_ul = False
        self.temp_ul = False
        self.temp_oh = False
        self.cond_ul = False
        self.cond_oh = False
        self.moist_ul = False
        self.moist_ll = False
        self.moist_hl = False
        self.moist_oh = False
        self.light_ul = False
        self.light_il = False
        self.light_oh = False
    
    def init_plant(self, plant,
                   temp_min, temp_max,
                   cond_min, cond_max,
                   moist_lo, moist_hi,
                   moist_min, moist_max,
                   light_min, light_irr, light_max):
        """
        Initialize plant data
        
        Parameters:
            plant (string):     name of the plant assigned to this sensor
            temp_min (float):   temperature [°C]
            temp_max (float):   temperature [°C]
            cond_min (int):     conductivity [µS/cm]
            cond_max (int):     conductivity [µS/cm]
            moist_lo (int):     moisture (inner limit) [%] 
            moist_hi (int):     moisture (inner limit) [%]
            moist_min (int):    moisture (outer limit) [%]
            moist_max (int):    moisture (outer limit) [%]
            light_min (int):    light [lux]
            light_irr (int):    light [lux]
            light_max (int):    light [lux]
        """       
        self.plant = plant
        self.temp_min = temp_min
        self.temp_max = temp_max
        self.cond_min = cond_min
        self.cond_max = cond_max
        self.moist_lo = moist_lo
        self.moist_hi = moist_hi
        self.moist_min = moist_min
        self.moist_max = moist_max
        self.light_min = light_min
        self.light_irr = light_irr
        self.light_max = light_max

    @property
    def timeout(self):
        return ((time() - self.tstamp) > self._tout)

    def update_sensor(self, temp, cond, moist, light, batt):
        """
        Update sensor data, timestamp and comparison flags
        
        Parameters:
            temp (float):     temperature [°C]
            cond (int):       conductivity [µS/cm]
            moist (int):      moisture [%]
            light (int):      light [lux]
            batt (int):       battery [%]
        """
        self.temp = temp
        self.cond = cond
        self.moist = moist
        self.light = light
        self.batt = batt
        self.tstamp = time()
        
        self.batt_ul = self.batt < self.batt_min
        self.temp_ul = self.temp < self.temp_min
        self.temp_oh = self.temp > self.temp_max
        self.cond_ul = self.cond < self.cond_min
        self.cond_oh = self.cond > self.cond_max
        self.moist_ul = self.moist < self.moist_min
        self.moist_ll = (self.moist < self.moist_lo) and (self.moist >= self.moist_min)
        self.moist_hl = (self.moist > self.moist_hi) and (self.moist <= self.moist_max)
        self.moist_oh = self.moist > self.moist_max
        self.light_ul = self.light < self.light_min
        self.light_il = self.light > self.light_irr
        self.light_oh = self.light > self.light_max

    def update_moisture_sensor(self, moist):
        """
        Update sensor data, timestamp and comparison flags
        
        Parameters:
            moist (int):      moisture [%]
        """
        self.moist = moist
        self.tstamp = time()
        
        self.moist_ul = self.moist < self.moist_min
        self.moist_ll = (self.moist < self.moist_lo) and (self.moist >= self.moist_min)
        self.moist_hl = (self.moist > self.moist_hi) and (self.moist <= self.moist_max)
        self.moist_oh = self.moist > self.moist_max

    def update_temperature_sensor(self, temp):
        """
        Update sensor data, timestamp and comparison flags
        
        Parameters:
            temp (float):     temperature [°C]
        """
        self.temp = temp
        self.tstamp = time()
        
        self.temp_ul = self.temp < self.temp_min
        self.temp_oh = self.temp > self.temp_max
    
    @property    
    def valid(self):
        """
        Check if data is valid
        
        Returns:
            bool: Sensor data has been updated initially and the last update occurred without timeout 
        """
        if (self.tstamp == 0):
            return (False)
        return ((time() - self.tstamp) < self._tout) 

    @property
    def data(self):
        """
        Format sensor data as JSON string
        
        Returns:
            string: Sensor data as JSON string
        """

        data = {}
        data['temperature']  = self.temp
        data['conductivity'] = self.cond
        data['moisture']     = self.moist
        data['light']        = self.light
        data['battery']      = self.batt
        return json.dumps(data)
