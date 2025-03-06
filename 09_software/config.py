###############################################################################
# config.py
#
# This module provides constants as default application settings
# and the class Settings which mostly provides attributes set
# from the configuration file.
#
# It is higly recommended to leave the constants as-is and to
# modify config.ini instead!!!
#
#
# created: 01/2021 updated: 06/2021
#
# This program is Copyright (C) 01/2021 Matthias Prinke
# <m.prinke@arcor.de> and covered by GNU's GPL.
# In particular, this program is free software and comes WITHOUT
# ANY WARRANTY.
#
# History:
#
# 20210117 Extracted from flora.py
# 20210208 Added more config items
# 20210209 Added inheritance from ConfigParser
# 20210211 Modified to save memory with MicroPython on ESP32
#          Changed to use own ConfigParser independend of execution environment
# 20210212 Moved 'secrets' to secrets.py
# 20210324 Improved memory handling by releasing chunks allocated by
#          ConfigParser as soon as possible and calling garbage collector
# 20210521 Added using micropython.const()
# 20210608 Added support of 2nd pump
# 20210622 Added MOIST_DIV, changed MOISTURE_MIN_VAL/MOISTURE_MAX_VAL to
#          real sensor output voltage in mV
# 20250306 Removed Removed alert/report/email configuration
#
# ToDo:
# - 
#
###############################################################################

import sys

if sys.implementation.name != "micropython":
    import os.path
else:
    from micropython import const

from ConfigParser import ConfigParser
from secrets import *


###############################################################################
# Constants (User Area)
###############################################################################
DEBUG               = const(0)     # False: 0 / True: 1
MEMINFO             = const(0)     # False: 0 / True: 1
VERBOSITY           = const(1)

WLAN_MAX_RETRIES    = const(5)     # max. no. of retries for (re-)connecting to WLAN
WLAN_RETRY_DELAY    = const(30)    # delay [s] between WLAN connect retries
BLE_MAX_RETRIES     = const(3)     # max. no. of retries for Bluetooth Low Energy devices
BLE_TIMEOUT         = const(12000) # timeout [ms] for Bluetooth Low Energy data access
BME280_ADDR         = const(0x76)  # I2C bus address for BME280 weather sensor

PROJECT_NAME        = 'flora'
PROJECT_VERSION     = 'V2.1.1'
PROJECT_BUILD       = '20240709'
PROJECT_URL         = 'https://github.com/matthias-bs/Flora2'


##############################################################################
# Constants (Expert Area)
##############################################################################

# GPIO settings
# Raspberry Pi
#GPIO_TANK_SENS_LOW   = const(23)
#GPIO_TANK_SENS_EMPTY = const(24)
#GPIO_PUMP_POWER      = [17, 27]
#GPIO_PUMP_STATUS     = const(22)
#GPIO_SENSOR_POWER    = const(18)
#GPIO_I2C_SDA         = const(26) # FIXME
#GPIO_I2C_SCL         = const(25) # FIXME

# ESP32-WROOM-32
GPIO_TANK_SENS_LOW   = const(23)
GPIO_TANK_SENS_EMPTY = const(21)
GPIO_PUMP_POWER      = [19, 18]
GPIO_PUMP_STATUS     = [99, 99] # dummy value, driver status not supported 
GPIO_SENSOR_POWER    = const(27)
GPIO_TEMP_SENS       = const(5)
GPIO_I2C_SDA         = const(26)
GPIO_I2C_SCL         = const(25)

# Config defaults
_MQTT_KEEPALIVE      = const(60)
_PROCESSING_PERIOD   = const(300)
_PROCESSING_PERIOD2  = const(600)
_MESSAGE_TIMEOUT     = const(900)
_NIGHT_BEGIN         = "24:00"
_NIGHT_END           = "00:00"
_AUTO_IRRIGATION     = const(1)
_IRR_DURATION_AUTO   = const(120)
_IRR_DURATION_MAN    = const(60)
_IRR_REST            = const(7200)
_BATT_LOW            = const(5)

# Constants for internal use
MQTT_DATA_RETAIN     = const(1)            # False: 0 / True: 1
MQTT_MAX_CYCLES      = const(20)           # max. no. of send/receive cycles
PUMP_BUSY_MAN        = const(1)
PUMP_BUSY_AUTO       = const(2)
MOISTURE_ADC_PINS    = [34, 35, 32, 33]
MOISTURE_MIN_VAL     = const(1250)
MOISTURE_MAX_VAL     = const(900)
UBATT_ADC_PIN        = const(35)           # ACD pin - mutually exclusive with any other use
UBATT_DIV            = 100/(100+200)       # Voltage divider R1 / (R1 + R2) -> V_meas = V(R1 + R2); V_adc = V(R1)
MOIST_DIV            = 330/(330+220)       # Voltage divider R1 / (R1 + R2) -> V_meas = V(R1 + R2); V_adc = V(R1)
VREF                 = None                # V_ref in mV or None for eFuse calibration value
UBATT_SAMPLES        = const(10)           # no. of samples for averaging


##############################################################################
# Global variables
##############################################################################
settings = None


###############################################################################
# Settings class - Global settings from config file, MQTT messages and others
###############################################################################
class Settings (ConfigParser):
    def __init__(self, config_dir, delimiters, inline_comment_prefixes):
        self.irr_scheduled = [False, False]
        
        cp = ConfigParser(delimiters, inline_comment_prefixes)
        cp.optionxform = str
        
        # Load configuration file
        if sys.implementation.name != "micropython":
            cp.read([os.path.join(config_dir, 'config.ini.dist'),
                     os.path.join(config_dir, 'config.ini')])
        else:
            cp.read('config.ini')
        
        # General
        self.processing_period  = cp.getint('General', 'processing_period',         fallback=_PROCESSING_PERIOD)
        self.processing_period2 = cp.getint('General', 'processing_period2',        fallback=_PROCESSING_PERIOD2)
        self.battery_weak       = cp.getint('General', 'battery_weak',              fallback=2400)
        self.battery_low        = cp.getint('General', 'battery_low',               fallback=0)
        self.sensor_batt_low    = cp.getint('General', 'sensor_batt_low',           fallback=_BATT_LOW)
        self.auto_irrigation    = cp.getboolean('General', 'auto_irrigation',       fallback=_AUTO_IRRIGATION)
        self.irr_duration_auto1 = cp.getint('General', 'irrigation_duration_auto1', fallback=_IRR_DURATION_AUTO)
        self.irr_duration_auto2 = cp.getint('General', 'irrigation_duration_auto2', fallback=_IRR_DURATION_AUTO)
        self.irr_duration_man   = cp.getint('General', 'irrigation_duration_man',   fallback=_IRR_DURATION_MAN)
        self.irr_rest           = cp.getint('General', 'irrigation_rest',           fallback=_IRR_REST)
        night_begin = cp.get('General', 'night_begin', fallback=_NIGHT_BEGIN)
        night_end   = cp.get('General', 'night_end',   fallback=_NIGHT_END)
        night_begin_hr, night_begin_min = night_begin.split(':')
        night_end_hr, night_end_min = night_end.split(':')
        self.night_begin_hr     = int(night_begin_hr)
        self.night_begin_min    = int(night_begin_min)
        self.night_end_hr       = int(night_end_hr)
        self.night_end_min      = int(night_end_min)
        self.deep_sleep         = cp.getboolean('General', 'deep_sleep',         fallback=False)
        self.daemon_enabled     = cp.getboolean('General', 'daemon_enabled',     fallback='True')
        cp.remove_section('General')

        # Sensors
        self.sensor_interface   = cp.get('Sensors', 'sensor_interface')
        self.temperature_sensor = cp.getboolean('Sensors', 'temperature_sensor', fallback=False)
        self.weather_sensor     = cp.getboolean('Sensors', 'weather_sensor',     fallback=False)
        self.battery_voltage    = cp.getboolean('Sensors', 'battery_voltage',    fallback=False)
        self.plant_sensors      = cp.get('Sensors', 'plant_sensors')
        cp.remove_section('Sensors')
        
        # MQTT
        self.mqtt_keepalive     = cp.getint('MQTT', 'keepalive',       fallback=_MQTT_KEEPALIVE)
        self.mqtt_msg_timeout   = cp.getint('MQTT', 'message_timeout', fallback=_MESSAGE_TIMEOUT)
        self.base_topic_sensors = cp.get('MQTT', 'base_topic_sensors', fallback='miflora-mqtt-daemon').lower()
        self.base_topic_flora   = cp.get('MQTT', 'base_topic_flora',   fallback='flora').lower()
        self.mqtt_server        = cp.get('MQTT', 'hostname')
        self.mqtt_port          = cp.getint('MQTT', 'port',            fallback=1883)
        self.mqtt_user          = cp.get('MQTT', 'username',           fallback=MQTT_USERNAME if MQTT_USERNAME else None)
        self.mqtt_password      = cp.get('MQTT', 'password',           fallback=MQTT_PASSWORD if MQTT_PASSWORD else None)
        self.mqtt_tls           = cp.getboolean('MQTT', 'tls',         fallback=False)
        self.mqtt_ca_cert       = cp.get('MQTT', 'tls_ca_cert',        fallback=None)
        self.mqtt_keyfile       = cp.get('MQTT', 'tls_keyfile',        fallback=None)
        self.mqtt_certfile      = cp.get('MQTT', 'tls_certfile',       fallback=None)
        cp.remove_section('MQTT')

        self.cp = cp

