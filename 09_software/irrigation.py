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
# created: 01/2021 updated: 07/2021
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
# 20210709 Bugfixes
# 20250402 Code improvements
# 20250404 Updated MQTT interface
#          Modified pump handling
#
# Backlog:
# - 
#
###############################################################################

import time
import pump
import sensor
from print_line import print_line
import config as cfg
from config import config, VERBOSITY

###############################################################################
# Irrigation class - Manual and automatic irrigation control
###############################################################################
class Irrigation:
    def __init__(self, mqtt_client):
        """
        The constructor for Irrigation class.
        """
        self.mqtt_client = mqtt_client

    ###################################################################################################
    # Handle manual irrigation
    ###################################################################################################
    def man_irrigation(self):
        """
        Manually run irrigation
        """
        # Check if flag has been set (asynchronously) in 'mqtt_man_irrigation_request' 
        # message callback function
        for i, p in enumerate(pump.pumps):
            if (p.busy == cfg.PUMP_BUSY_MAN):
                print_line('Running pump #{} for {:d} seconds -->'.format(i+1, config.irr_duration_man),
                           console=True, sd_notify=True)
                p.power_on(config.irr_duration_man)
                p.busy = 0
                self.mqtt_client.publish(config.base_topic_flora + '/man_irr_stat', str(0), qos = 1)
                print_line(f'<-- Running pump #{i+1} finished, Status: {p.status_str}',
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
        (yy, mm, dd, _, _, s, dow, doy) = time.localtime()
        h = config.night_begin_hr
        m = config.night_begin_min
        nighttime_start = time.mktime((yy, mm, dd, h, m, s, dow, doy))

        h = config.night_end_hr
        m = config.night_end_min
        nighttime_end = time.mktime((yy, mm, dd, h, m, s, dow, doy))

        now = time.mktime(time.localtime())
        if ((now >= nighttime_start) or (now < nighttime_end)):
            if (VERBOSITY > 1):
                print_line("auto_irrigation: sleep time! Zzzz...")
            return [False, False]

        # Evaluate per pump
        activate = [False, False]
        for i, _ in enumerate(pump.pumps):
            for s in sensor.sensors:
                if sensor.sensors[s].pump != i+1:
                    continue
                if sensor.sensors[s].valid == False:
                    # At least one sensor with timeout -> bail out
                    break
                if sensor.sensors[s].light_il:
                    # At least one light value over irrigation limit -> bail out
                    break
                if sensor.sensors[s].moist_oh:
                    # At least one moisture value over range -> bail out 
                    activate[i] = False
                    break
                if sensor.sensors[s].moist_ul:
                    # At least one moisture value under range -> ready!
                    activate[i] = True
                # Else: All moisture values (regarding this pump) within desired range -> nothing to do!
        
        schedule = [False, False]
        for i, p in enumerate(pump.pumps):
            if activate[i]:
                if (time.time() - p.timestamp) < config.irr_rest:
                    # All sensor values are within range, but time since last irrigation (irr_rest)
                    # has not expired yet -> bailing out
                    if VERBOSITY > 1:
                        print_line(f"Auto irrigation: pump #{i} scheduled.")
                    schedule[i] = True
                elif p.busy == 0:
                    # Pump has not been started manually - ready!
                    duration = config.irr_duration_auto1 if (i == 0) else config.irr_duration_auto2
                    print_line(f"Auto irrigation: running pump #{p+1} for {duration:d} seconds",
                            console=True, sd_notify=True)
                    p.busy = cfg.PUMP_BUSY_AUTO
                    p.power_on(duration)
                    p.busy = 0
                    p.timestamp = time.time()
        
        return schedule
