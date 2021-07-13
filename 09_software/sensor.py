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
# created: 01/2021 updated: 07/2021
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
# 20210509 Added attribute address
# 20210523 Added config_error()
# 20210605 Added attribute pump
# 20210609 Added property <state>
# 20210712 Fixed setting of attribute pump in init_plant() -> integer!
#
# ToDo:
# - 
#
###############################################################################

from time import time
from print_line import print_line

import json
import config as m_config

##############################################################################
# Global variables
##############################################################################
sensors = None

def config_error(sensor):
    for option in [ 'name',
                'pump',
                'temp_min', 
                'temp_max',
                'cond_min',
                'cond_max',
                'moist_min',
                'moist_lo',
                'moist_hi',
                'moist_max',
                'light_min',
                'light_irr',
                'light_max']:
        if (not(m_config.settings.cp.has_option(sensor, option))):
            print_line('The configuration file "config.ini" has a section "[' + sensor + ']",',
                       error=True, sd_notify=True)
            print_line('but the key "' + option + '" is missing.',
                       error=True, sd_notify=True)
            return True
    
    if (m_config.settings.sensor_interface == 'ble'):
        if (not(m_config.settings.cp.has_option(sensor, 'address'))):                
            print_line('The configured plant sensor interface is Bluetooth LE,')
            print_line('the configuration file "config.ini" has a section "[' + sensor + ']",',
                        error=True, sd_notify=True)
            print_line('but the mandatory key "address" is missing.',
                        error=True, sd_notify=True)
            return True
    return False

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
        address (string):   Bluetooth LE address
        pump (int):         pump serving this plant 
        tstamp (int):       timestamp of last sensor data reception
        plant (string):     name of the plant assigned to this sensor
        batt_min (int):     minimum battery level [%]
        _tout (int):        max. time between data updates
    
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
        self.pump = 0
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
            
    def init_plant(self):
        """
        Initialize plant data
        """
        sensor = self.name
        self.plant     = m_config.settings.cp.get(sensor, 'name')
        self.pump      = m_config.settings.cp.getint(sensor, 'pump')
        self.temp_min  = m_config.settings.cp.getfloat(sensor, 'temp_min')
        self.temp_max  = m_config.settings.cp.getfloat(sensor, 'temp_max')
        self.cond_min  = m_config.settings.cp.getint(sensor, 'cond_min')
        self.cond_max  = m_config.settings.cp.getint(sensor, 'cond_max')
        self.moist_min = m_config.settings.cp.getint(sensor, 'moist_min')
        self.moist_lo  = m_config.settings.cp.getint(sensor, 'moist_lo')       
        self.moist_hi  = m_config.settings.cp.getint(sensor, 'moist_hi')
        self.moist_max = m_config.settings.cp.getint(sensor, 'moist_max')
        self.light_min = m_config.settings.cp.getint(sensor, 'light_min')
        self.light_irr = m_config.settings.cp.getint(sensor, 'light_irr')
        self.light_max = m_config.settings.cp.getint(sensor, 'light_max')


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

    @property
    def state(self):
        """Return state (for saving to RTC RAM)"""
        return self.tstamp
    
    @state.setter
    def state(self, var):
        """Set state (for loading from RTC RAM)"""
        self.tstamp = var
