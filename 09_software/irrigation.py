###############################################################################
# irrigation.py
#
# This module provides the Irrigation class
#
# - manual irrigation (triggered by the flag pump.busy)
# - auto irrigation, depending on
#   - current time of day (disabled during night time)
#   - various sensor values
#   - rest time after previous irrigation
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
# 20210202 Modified for compatibility with MicroPython
# 20210324 Changed access to global data structures
# 20210327 Added more workarounds for MicroPython restrictions
# 20210605 Added support of 2nd pump
# 20210809 Bugfixes
#
# ToDo:
# - 
#
###############################################################################

import time
import config as cfg
import flora_mqtt as mqtt
import pump as m_pump
import sensor as m_sensor
from print_line import *
from config import DEBUG, VERBOSITY

###############################################################################
# Irrigation class - Manual and automatic irrigation control
###############################################################################
class Irrigation:
    def __init__(self):
        """
        The constructor for Irrigation class.
        """
        pass

    ###################################################################################################
    # Handle manual irrigation
    ###################################################################################################
    def man_irrigation(self):
        """
        Manually run irrigation
        """
        # Check if flag has been set (asynchronously) in 'mqtt_man_irrigation_request' 
        # message callback function
        for i in range(2):
            if (m_pump.pumps[i].busy == cfg.PUMP_BUSY_MAN):
                print_line('Running pump #{} for {:d} seconds -->'.format(i+1, cfg.settings.irr_duration_man),
                           console=True, sd_notify=True)
                m_pump.pumps[i].power_on(cfg.settings.irr_duration_man)
                m_pump.pumps[i].busy = 0
                mqtt.mqtt_client.publish(cfg.settings.base_topic_flora + '/man_irr_stat', str(0), qos = 1)
                print_line('<-- Running pump #{} finished, Status: {}'.format(i+1, m_pump.pumps[i].status_str), 
                            console=True, sd_notify=True)


    ###################################################################################################
    # Handle automatic irrigation
    ###################################################################################################
    def auto_irrigation(self):
        """
        Automatically run irrigation -
        depending on sensor values, time of day and time since last irrigation

        Irrigation is run (per pump) if
        - current time is not within night time range
        - all sensor data is up-to-date
        - light is below the limit <light_irr> (to avoid sunburns)
        - at least one moisture level is below minimum,
          but none is above maximum

        The irrigation is done immediately if the rest time <irr_rest>
        since the last (automatic) irrigation has expired, otherwise it is
        scheduled until later.
        
        Returns:
            bool:   true  if irrigation is scheduled
                    false otherwise
        """
        # Skip automatic irrigation during night time
        # FIXME there is room for improvements...
        #now = datetime.now()
        #nighttime_start = now.replace(hour=settings.night_begin_hr, minute=settings.night_begin_min, second=0, microsecond=0)
        #nighttime_end = now.replace(hour=settings.night_end_hr, minute=settings.night_end_min, second=0, microsecond=0)
        (yy, mm, dd, h, m, s, dow, doy) = time.localtime()
        #print('auto_irrigation(): now = {}'.format(n))
        #now['tm_hour'] = settings.night_begin_hr
        #now['tm_min'] = settings.night_begin_min
        h = cfg.settings.night_begin_hr
        m = cfg.settings.night_begin_min

        nighttime_start = time.mktime((yy, mm, dd, h, m, s, dow, doy))
        #now['tm_hour'] = settings.night_end_hr
        #now['tm_min'] = settings.night_end_min
        h = cfg.settings.night_end_hr
        m = cfg.settings.night_end_min
        nighttime_end = time.mktime((yy, mm, dd, h, m, s, dow, doy))

        now = time.mktime(time.localtime())
        if ((now >= nighttime_start) or (now < nighttime_end)):
            if (VERBOSITY > 1):
                print_line("auto_irrigation: sleep time! Zzzz...")
            return [False, False]

        # Evaluate per pump
        activate = [False, False]
        for p in range(2):
            for sensor in m_sensor.sensors:
                if (m_sensor.sensors[sensor].pump != p+1):
                    continue
                if (m_sensor.sensors[sensor].valid == False):
                    # At least one sensor with timeout -> bail out
                    break
                if (m_sensor.sensors[sensor].light_il):
                    # At least one light value over irrigation limit -> bail out
                    break
                if (m_sensor.sensors[sensor].moist_oh):
                    # At least one moisture value over range -> bail out 
                    break
                if (m_sensor.sensors[sensor].moist_ul):
                    # At least one moisture value under range -> ready!
                    activate[p] = True
                    break
                # Else: All moisture values (regarding this pump) within desired range -> nothing to do!
        
        schedule = [False, False]
        for p in range(2):
            if activate[p]:
                if ((time.time() - m_pump.pumps[p].timestamp) < cfg.settings.irr_rest):
                    # All sensor values are within range, but time since last irrigation (irr_rest)
                    # has not expired yet -> bailing out
                    if (VERBOSITY > 1):
                        print_line("Auto irrigation: pump #{} scheduled.".format(p))
                    schedule[p] = True
                elif (m_pump.pumps[p].busy == 0):
                    # Pump has not been started manually - ready!
                    duration = cfg.settings.irr_duration_auto1 if (p == 0) else cfg.settings.irr_duration_auto2
                    print_line("Auto irrigation: running pump #{} for {:d} seconds"
                            .format(p+1, duration), console=True, sd_notify=True)
                    m_pump.pumps[p].busy = cfg.PUMP_BUSY_AUTO
                    m_pump.pumps[p].power_on(duration)
                    m_pump.pumps[p].busy = 0
                    m_pump.pumps[p].timestamp = time.time()
        
        return schedule
