###############################################################################
# report.py
#
# This module provides the Report class
# 
# - generates HTML report with various sensor/plant and system data
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
# 20210118 Extracted from flora.py
# 20210103 Added workarounds for MicroPython
# 20210204 Fixed time/date calculation and output
#          Added client name <base_topic_flora> to report
# 20210207 Changed to send email in smaller chunks
#          due to ESP memory constraints
# 20210316 Added reduced sensor status report in case only
#          analog moisture sensors are used 
# 20210321 Changed 'analog' sensors to 'local' sensors in configuration,
#          added option for temperature sensor,
#          added garbage collection
# 20210607 Added support for 2nd pump
# 20240305 Removed email support, added JSON output for MQTT
#
# ToDo:
#
# - 
#
###############################################################################

import sys
import json

if sys.implementation.name != "micropython":
    from time import strftime

from garbage_collect import gcollect, meminfo
import config as m_config
import pump as m_pump
import sensor as m_sensor
import tank as m_tank
from time import time, localtime


###############################################################################
# Report class - Generate status report  
###############################################################################
class Report:
    """
    Generate status report
    
    Attributes:
        email         (Email):      instance of Email class
        min_light_irr (int):        smallest light intensity which still allows irrigation
    """
    def __init__(self):
        """
        The constructor for Report class.
        """
        
        self.data = {}
        
    def gen_report(self):
        """
        Generate report
        """
        self.data['timestamp'] = self.date_time_str(localtime())
        
        # Find minimum light_irr value of all sensors
        self.min_light_irr = 1000000
        for s in m_sensor.sensors:
            self.min_light_irr = min(self.min_light_irr, m_sensor.sensors[s].light_irr)

        self.sensor_settings()
        self.system_status()
        self.system_settings()
        return json.dumps(self.data)

    def date_time_str(self, dt):
        """
        Output date and time as string
        
        Parameters:
            dt (date-time tuple): (year, month, mday, hour, minute, second, weekday, yearday)
            
        Returns:
            string: date/time considering locale (Python) or fixed format dd.mm.yy hh:mm (MicroPython)
        """
        if sys.implementation.name != "micropython":
            # neatly print time and date using locale settings
            return strftime("%x %X")
        else:
            # lean approach with restrictions from MicroPython's utime: dd.mm.yy hh:mm
            # date-time = (year, month, mday, hour, minute, second, weekday, yearday)
            return '{:02d}.{:02d}.{} {:02d}:{:02d}'.format(dt[2], dt[1], dt[0], dt[3], dt[4])

    def sensor_settings(self):
        """
        Add sensor (and plant) settings
        """
        for sensor in m_sensor.sensors:
            s = m_sensor.sensors[sensor]
            self.data[s.name] = {}
            self.data[s.name]['settings'] = {}
            self.data[s.name]['settings']['plant'] = s.plant
            self.data[s.name]['settings']['moist_min'] = s.moist_min
            self.data[s.name]['settings']['moist_lo'] = s.moist_lo
            self.data[s.name]['settings']['moist_hi'] = s.moist_hi
            self.data[s.name]['settings']['moist_max'] = s.moist_max
            self.data[s.name]['settings']['temp_min'] = s.temp_min
            self.data[s.name]['settings']['temp_max'] = s.temp_max
            self.data[s.name]['settings']['cond_min'] = s.cond_min
            self.data[s.name]['settings']['cond_max'] = s.cond_max
            self.data[s.name]['settings']['light_min'] = s.light_min
            self.data[s.name]['settings']['light_max'] = s.light_max
            self.data[s.name]['settings']['batt_min'] = s.batt_min

            if s.valid:
                self.data[s.name]['status'] = {}
                self.data[s.name]['status']['batt_ul'] = s.batt_ul
                if m_config.settings.temperature_sensor:
                    self.data[s.name]['status']['temp_ul'] = s.temp_ul
                    self.data[s.name]['status']['temp_oh'] = s.temp_oh
                
                self.data[s.name]['status']['moist_ul'] = s.moist_ul
                self.data[s.name]['status']['moist_ll'] = s.moist_ll
                self.data[s.name]['status']['moist_ul'] = s.moist_ul
                self.data[s.name]['status']['moist_oh'] = s.moist_oh
                self.data[s.name]['status']['cond_ul'] = s.cond_ul
                self.data[s.name]['status']['cond_oh'] = s.cond_oh
                self.data[s.name]['status']['light_ul'] = s.cond_ul
                self.data[s.name]['status']['light_oh'] = s.cond_oh

    def system_status(self):
        """
        Add system status to report.
        """
        self.data['irrigation'] = []
        for i in range(2):
            if (m_pump.pumps[i].timestamp != 0):
                last_irrigation = self.date_time_str(localtime(m_pump.pumps[i].timestamp))
                next_irrigation = self.date_time_str(localtime(m_pump.pumps[i].timestamp + m_config.settings.irr_rest))
                scheduled = m_config.settings.irr_scheduled[i]
                self.data['irrigation'].append({'last': last_irrigation, 'next': next_irrigation, 'scheduled': scheduled})

        self.data['pump'] = []
        for i in range(2):
            if (m_pump.pumps[i].status == 2):
                status = "on: error"
            elif (m_pump.pumps[i].status == 4):
                status = "off: error"
            else:
                status = "ok"
            self.data['pump'].append(status)

        tank_status = ['empty', 'low', 'ok']
        self.data['tank'] = tank_status[m_tank.tank.status]

    def system_settings(self):
        """
        Add system settings (HTML table) to report.
        """
        self.data['irrigation'] = {}
        self.data['irrigation']['auto_enabled'] = m_config.settings.auto_irrigation
        self.data['irrigation']['auto_duration'] = []
        self.data['irrigation']['auto_duration'].append(m_config.settings.irr_duration_auto1)
        self.data['irrigation']['auto_duration'].append(m_config.settings.irr_duration_auto2)
        self.data['irrigation']['man_duration'] = m_config.settings.irr_duration_man
        self.data['irrigation']['auto_rest'] = m_config.settings.irr_rest
        self.data['irrigation']['auto_max_light'] = self.min_light_irr
