###############################################################################
# settings.py
#
# This module provides constants as default application settings
# and the class Settings which mostly provides attributes set
# from the configuration file.
#
# It is higly recommended to leave the constants as-is and to
# modify config.ini instead!!!
#
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
# 20210208 Added more config items
# 20210209 Added inheritance from ConfigParser
# 20210211 Modified to save memory with MicroPython on ESP32
#          Changed to use own ConfigParser independend of execution environment
# 20210212 Moved 'secrets' to secrets.py
# 20210324 Improved memory handling by releasing chunks allocated by
#          ConfigParser as soon as possible and calling garbage collector
#
# ToDo:
# - 
#
###############################################################################

import sys

if sys.implementation.name != "micropython":
    import os.path

from ConfigParser import ConfigParser
from secrets import *
from garbage_collect import gcollect


###############################################################################
# Constants
###############################################################################
DEBUG               = False
MEMINFO             = False
VERBOSITY           = 1

WLAN_MAX_RETRIES    = 5     # max. no. of retries for (re-)connecting to WLAN
WLAN_RETRY_DELAY    = 30    # delay [s] between WLAN connect retries
BLE_MAX_RETRIES     = 3     # max. no. of retries for Bluetooth Low Energy devices
BLE_TIMEOUT         = 12000 # timeout [ms] for Bluetooth Low Energy data access
BME280_ADDR         = 0x76  # I2C bus address for BME280 weather sensor

PROJECT_NAME        = 'flora'
PROJECT_VERSION     = 'V2.0'
PROJECT_URL         = '<tbd>'

##############################################################################
# Global variables
##############################################################################
#station  = None
#local_ap = None
settings = None

# GPIO settings
if sys.implementation.name != "micropython":
    GPIO_TANK_SENS_LOW   = 23
    GPIO_TANK_SENS_EMPTY = 24
    GPIO_PUMP_POWER      = 17
    GPIO_PUMP_STATUS     = 22
    GPIO_SENSOR_POWER    = 18
    GPIO_I2C_SDA         = 26 # FIXME
    GPIO_I2C_SCL         = 25 # FIXME
else:
    GPIO_TANK_SENS_LOW   = 23
    GPIO_TANK_SENS_EMPTY = 21
    GPIO_PUMP_POWER      = 19
    GPIO_PUMP_STATUS     = 99
#    GPIO_PUMP_STATUS     = 5
    GPIO_SENSOR_POWER    = 27
    GPIO_TEMP_SENS       = 5
    GPIO_I2C_SDA         = 26
    GPIO_I2C_SCL         = 25

# Config defaults
_MQTT_KEEPALIVE      = 60
_PROCESSING_PERIOD   = 300
_MESSAGE_TIMEOUT     = 900
_NIGHT_BEGIN         = "24:00"
_NIGHT_END           = "00:00"
_AUTO_REPORT         = 1
_AUTO_IRRIGATION     = 1
_IRR_DURATION_AUTO   = 120
_IRR_DURATION_MAN    = 60
_IRR_REST            = 7200
_ALERTS_DEFER_TIME   = 4
_ALERTS_REPEAT_TIME  = 24
_ALERT_MODE_DEFAULT  = 2
_BATT_LOW            = 5

# Constants for internal use
PUMP_BUSY_MAN       = 1
PUMP_BUSY_AUTO      = 2
MOISTURE_ADC_PINS   = [34, 35, 32, 33]
MOISTURE_MIN_VAL    = 220
MOISTURE_MAX_VAL    = 60
UBATT_ADC_PIN       = 35            # ACD pin - mutually exclusive with any other use
UBATT_DIV           = 100/(100+200) # Voltage divider R1 / (R1 + R2) -> V_meas = V(R1 + R2); V_adc = V(R1)
VREF                = 1065          # V_ref in mV (device specific value -> espefuse.py --port <port> adc_info)
UBATT_SAMPLES       = 10            # no. of samples for averaging


###############################################################################
# Settings class - Global settings from config file, MQTT messages and others
###############################################################################
class Settings (ConfigParser):
    def __init__(self, config_dir, delimiters, inline_comment_prefixes):
        self.irr_scheduled = False
        
        ConfigParser.__init__(self, delimiters, inline_comment_prefixes)
        self.optionxform = str
        
        # Load configuration file
        if sys.implementation.name != "micropython":
            self.read([os.path.join(config_dir, 'config.ini.dist'),
                       os.path.join(config_dir, 'config.ini')])
        else:
            self.read('config.ini')
        
        # General
        self.processing_period  = self.getint('General', 'processing_period',        fallback=_PROCESSING_PERIOD)
        self.sensor_batt_low    = self.getint('General', 'batt_low',                 fallback=_BATT_LOW)
        self.auto_report        = self.getboolean('General', 'auto_report',          fallback=_AUTO_REPORT)
        self.auto_irrigation    = self.getboolean('General', 'auto_irrigation',      fallback=_AUTO_IRRIGATION)
        self.irr_duration_auto  = self.getint('General', 'irrigation_duration_auto', fallback=_IRR_DURATION_AUTO)
        self.irr_duration_man   = self.getint('General', 'irrigation_duration_man',  fallback=_IRR_DURATION_MAN)
        self.irr_rest           = self.getint('General', 'irrigation_rest',          fallback=_IRR_REST)
        night_begin = self.get('General', 'night_begin', fallback=_NIGHT_BEGIN)
        night_end   = self.get('General', 'night_end',   fallback=_NIGHT_END)
        night_begin_hr, night_begin_min = night_begin.split(':')
        night_end_hr, night_end_min = night_end.split(':')
        self.night_begin_hr     = int(night_begin_hr)
        self.night_begin_min    = int(night_begin_min)
        self.night_end_hr       = int(night_end_hr)
        self.night_end_min      = int(night_end_min)
        self.sensor_interface   = self.get('General', 'sensor_interface')
        self.temperature_sensor = self.getboolean('General', 'temperature_sensor', fallback=False)
        self.weather_sensor     = self.getboolean('General', 'weather_sensor',     fallback=False)
        self.battery_voltage    = self.getboolean('General', 'battery_voltage',    fallback=False)
        self.deep_sleep         = self.getboolean('General', 'deep_sleep',         fallback=False)
        self.remove_section('General')
        gcollect()
        
        # Daemon
        self.daemon_enabled     = self.getboolean('Daemon', 'enabled', fallback='yes')
        
        # MQTT
        self.mqtt_keepalive     = self.getint('MQTT', 'keepalive',       fallback=_MQTT_KEEPALIVE)
        self.mqtt_msg_timeout   = self.getint('MQTT', 'message_timeout', fallback=_MESSAGE_TIMEOUT)
        self.base_topic_sensors = self.get('MQTT', 'base_topic_sensors', fallback='miflora-mqtt-daemon').lower()
        self.base_topic_flora   = self.get('MQTT', 'base_topic_flora',   fallback='flora').lower()
        self.mqtt_server        = self.get('MQTT', 'hostname')
        self.mqtt_port          = self.getint('MQTT', 'port',      fallback=1883)
        self.mqtt_user          = self.get('MQTT', 'username',     fallback=MQTT_USERNAME if MQTT_USERNAME else None)
        self.mqtt_password      = self.get('MQTT', 'password',     fallback=MQTT_PASSWORD if MQTT_PASSWORD else None)
        self.mqtt_tls           = self.getboolean('MQTT', 'tls',   fallback=False)
        self.mqtt_ca_cert       = self.get('MQTT', 'tls_ca_cert',  fallback=None)
        self.mqtt_keyfile       = self.get('MQTT', 'tls_keyfile',  fallback=None)
        self.mqtt_certfile      = self.get('MQTT', 'tls_certfile', fallback=None)
        self.mqtt_sensors       = self.get('MQTT', 'sensors')
        self.remove_section('MQTT')
        gcollect()
        
        # Alerts
        self.alerts_defer_time     = self.getint('Alerts', 'alerts_defer_time',  fallback=_ALERTS_DEFER_TIME) * 3600
        self.alerts_repeat_time    = self.getint('Alerts', 'alerts_repeat_time', fallback=_ALERTS_REPEAT_TIME) * 3600
        self.alerts_w_battery      = self.getint('Alerts', 'w_battery',          fallback=_ALERT_MODE_DEFAULT)
        self.alerts_w_temperature  = self.getint('Alerts', 'w_temperature',      fallback=_ALERT_MODE_DEFAULT)
        self.alerts_w_moisture     = self.getint('Alerts', 'w_moisture',         fallback=_ALERT_MODE_DEFAULT)
        self.alerts_i_moisture     = self.getint('Alerts', 'i_moisture',         fallback=_ALERT_MODE_DEFAULT)
        self.alerts_w_conductivity = self.getint('Alerts', 'w_conductivity',     fallback=_ALERT_MODE_DEFAULT)
        self.alerts_w_light        = self.getint('Alerts', 'w_light',            fallback=_ALERT_MODE_DEFAULT)
    
        # Init system alerts
        self.alerts_e_sensor       = self.getint('Alerts', 'e_sensor',           fallback=_ALERT_MODE_DEFAULT)
        self.alerts_e_pump         = self.getint('Alerts', 'e_pump',             fallback=_ALERT_MODE_DEFAULT)
        self.alerts_e_tank_low     = self.getint('Alerts', 'e_tank_low',         fallback=_ALERT_MODE_DEFAULT)
        self.alerts_e_tank_empty   = self.getint('Alerts', 'e_tank_empty',       fallback=_ALERT_MODE_DEFAULT)
        self.remove_section('Alerts')
        gcollect()
        
        # Email
        self.smtp_server   = self.get('Email', 'smtp_server')
        self.smtp_port     = self.getint('Email', 'smtp_port')
        self.smtp_login    = self.get('Email', 'smtp_login',    fallback=SMTP_LOGIN)
        self.smtp_passwd   = self.get('Email', 'smtp_passwd',   fallback=SMTP_PASSWD)
        self.smtp_email    = self.get('Email', 'smtp_email',    fallback=SMTP_EMAIL)
        self.smtp_receiver = self.get('Email', 'smtp_receiver', fallback=SMTP_RECEIVER)
        self.remove_section('Email')
        gcollect()
        
