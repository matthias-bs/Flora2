###############################################################################
# report.py
#
# This module provides the Report class
# 
# - generates HTML report with various sensor/plant and system data
#
# created: 01/2021 updated: 03/2021
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
#
# ToDo:
#
# - 
#
###############################################################################

import sys

if sys.implementation.name != "micropython":
    from time import strftime
    
from flora_email import *
from time import time, localtime
from garbage_collect import gcollect, meminfo

###############################################################################
# Report class - Generate status report  
###############################################################################
class Report:
    """
    Generate status report
    
    Attributes:
        settings      (Settings):   instance of Settings class
        sensors       (Sensor{}):   dictionary of Sensor class
        tank          (Tank):       instance of Tank class
        pump          (Pump):       instance of Pump class
        email         (Email):      instance of Email class
        min_light_irr (int):        smallest light intensity which still allows irrigation
    """
    def __init__(self, settings, sensors, tank, pump):
        """
        The constructor for Report class.
        
        Parameters:
            settings (Settings):     instance of Settings class 
            sensors  (Sensor{}):     dictionary of Sensor class
            tank     (Tank):         instance of Tank class
            pump     (Pump):         instance of Pump class
        """
        self.settings = settings
        self.sensors = sensors
        self.tank = tank
        self.pump = pump
        gcollect()
        
        # Find minimum light_irr value of all sensors
        self.min_light_irr = 1000000
        for s in sensors:
            self.min_light_irr = min(self.min_light_irr, sensors[s].light_irr)


        # Create Email object
        self.email = Email(settings)
        
        # Connect to SMTP server and log in 
        if (self.email.smtp_begin()):
            # Create and send report
            self.header()
            gcollect()
            self.sensor_status()
            gcollect()
            self.system_status()
            gcollect()
            self.footer()
            
            # Finalize mail and disconnect from SMTP server
            self.email.smtp_finish()


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
        
        
    def header(self):
        """
        Generate HTML header for email report.
        """
        self.email.smtp_write('<!DOCTYPE html>\n')
        self.email.smtp_write('<html>\n')
        self.email.smtp_write('<head>\n')
        self.email.smtp_write('<title>Flora Status Report</title>\n')
        self.email.smtp_write('</head>\n')
        self.email.smtp_write('<body>\n')
        self.email.smtp_write('<h1>Flora Status Report</h1>\n')
        
        self.email.smtp_write('erstellt: {} von {}<br><br>\n'.format(self.date_time_str(localtime()), self.settings.base_topic_flora))


    def sensor_status(self):
        """
        Add sensor (and plant) status (HTML table) to report.

        The background color of table cells is set to orange for notifications
        and to red for alerts.
        """
        complete_data = (self.settings.sensor_interface != 'local')
        self.email.smtp_write('<table border="1">\n')
        self.email.smtp_write('<tr><th>Sensor<th>Soll/Ist<th>Feuchte [%]')
        if (self.settings.temperature_sensor):
            self.email.smtp_write('<th>Temperatur [&deg;C]')
        if (complete_data):
            self.email.smtp_write('<th>Leitf. [µS/cm]<th>Licht [lux]</tr>\n')
        self.email.smtp_write('</tr>\n')

        for sensor in self.sensors:
            s = self.sensors[sensor]
            self.email.smtp_write('<tr>\n')
            self.email.smtp_write('<td>{:s} ({:s})'.format(s.name, s.plant))
            self.email.smtp_write('<td>Soll')
            self.email.smtp_write('<td align="center">{:3.0f} ... [{:3.0f} ...{:3.0f}] ...{:3.0f}'\
                                  .format(s.moist_min, s.moist_lo, s.moist_hi, s.moist_max))
            if (self.settings.temperature_sensor):
                self.email.smtp_write('<td align="center">{:3.0f} ... {:3.0f}'.format(s.temp_min, s.temp_max))
            if (complete_data):
                self.email.smtp_write('<td align="center">{:4.0f} ... {:4.0f}'.format(s.cond_min, s.cond_max))
                self.email.smtp_write('<td align="center">{:6.0f} ... {:6.0f}'.format(s.light_min, s.light_max))
            self.email.smtp_write('</tr>\n')
            self.email.smtp_write('<tr>\n')

            if (s.valid == False):
                self.email.smtp_write('<td bgcolor="grey">-<td>Ist')
                self.email.smtp_write('<td align="center" bgcolor="grey">-')
                if (self.settings.temperature_sensor):
                    self.email.smtp_write('<td align="center" bgcolor="grey">-')
                if (complete_data):
                    self.email.smtp_write('<td align="center" bgcolor="grey">-')
                    self.email.smtp_write('<td align="center" bgcolor="grey">-')
            else:
                if (s.batt_ul):
                    col = "red"
                else:
                    col = "white"
                if (complete_data):
                    self.email.smtp_write('<td bgcolor="{:s}">Batt:{:3.0f} %\n'\
                                          .format(col, s.batt))
                else:
                    self.email.smtp_write('<td>\n')
                self.email.smtp_write('<td>Ist\n')
                if (s.moist_ll or s.moist_hl):
                    col = "orange"
                elif (s.moist_ul or s.moist_oh):
                    col = "red"
                else:
                    col = "white"
                self.email.smtp_write('<td align="center" bgcolor="{:s}">{:3.0f}\n'\
                                      .format(col, s.moist))

                if (self.settings.temperature_sensor):
                    if (s.temp_ul or s.temp_oh):
                        col = "red"
                    else:
                        col = "white"
                    self.email.smtp_write('<td align="center" bgcolor="{:s}">{:3.0f}\n'\
                                        .format(col, s.temp))
                if (complete_data):
                    if (s.cond_ul or s.cond_oh):
                        col = "red"
                    else:
                        col = "white"
                    self.email.smtp_write('<td align="center" bgcolor="{:s}">{:3.0f}\n'\
                                        .format(col, s.cond))

                    if (s.light_ul or s.light_oh):
                        col = "red"
                    else:
                        col = "white"
                    self.email.smtp_write('<td align="center" bgcolor="{:s}">{:3.0f}\n'\
                                        .format(col, s.light))
            
            self.email.smtp_write('</tr>\n')
        # END: for s in sensor_list:
        self.email.smtp_write('</table>\n')


    def system_status(self):
        """
        Add system status (HTML table) to report.
        """
        self.email.smtp_write('<h2>Systemstatus</h2>\n')
        self.email.smtp_write('<table border="1">\n')
        self.email.smtp_write('<tr><td>Automatische Benachrichtigung<td align="right">{:}</tr>\n'
                              .format("Ein" if(self.settings.auto_report) else "Aus"))
        self.email.smtp_write('<tr><td>Automatische Bew&auml;sserung<td align="right">{:}</tr>\n'
                              .format("Ein" if (self.settings.auto_irrigation) else "Aus"))
        self.email.smtp_write('<tr><td>Bew&auml;sserungsdauer (autom.) [s]<td align="right">{:d}</tr>\n'
                              .format(self.settings.irr_duration_auto))
        self.email.smtp_write('<tr><td>Bew&auml;sserungsdauer (manuell) [s]<td align="right">{:d}</tr>\n'
                              .format(self.settings.irr_duration_man))
        self.email.smtp_write('<tr><td>Pause nach Bew&auml;sserung [s]<td align="right">{:d}</tr>\n'
                              .format(self.settings.irr_rest))    
        self.email.smtp_write('<tr><td>max. Beleuchtungsst&auml;rke [lx]<td align="right">{:d}</tr>\n'
                              .format(self.min_light_irr))
        last_irrigation = "-" if (self.pump.timestamp == 0) \
                              else self.date_time_str(localtime(self.pump.timestamp))

        self.email.smtp_write('<tr><td>letzte automatische Bew&auml;sserung<td align="right">{:s}</tr>\n'
                              .format(last_irrigation))

        if (self.pump.timestamp != 0):
            next_irrigation = self.date_time_str(localtime(self.pump.timestamp + self.settings.irr_rest))
        else:
            next_irrigation = "-"
        self.email.smtp_write('<tr><td>n&auml;chste Bew&auml;sserung fr&uuml;hestens<td align="right">{:s}</tr>\n'
                              .format(next_irrigation))

        self.email.smtp_write('<tr><td>Bew&auml;sserung geplant<td align="right">{:s}</tr>\n'
                              .format("Ja" if self.settings.irr_scheduled else "Nein"))

        if (self.tank.empty):
            tank_status = "leer"
            col = "red"
        elif (self.tank.low):
            col = "orange"
            tank_status = "niedrig"
        else:
            col = "white"
            tank_status = "i.O."

        self.email.smtp_write('<tr><td>Status Tank<td align="right" bgcolor="{:s}">{:s}</tr>\n'
                              .format(col, tank_status))

        if (self.pump.status == 2):
            col = "red"
            pump_status_str = "on: error"
        elif (self.pump.status == 4):
            col = "red"
            pump_status_str = "off: error"
        else:
            col = "white"
            pump_status_str = "i.O."

        self.email.smtp_write('<tr><td>Status Pumpe<td align="right" bgcolor="{:s}">{:s}</tr>\n'
                              .format(col, pump_status_str))

        next_alert = time() + min(self.settings.alerts_defer_time, self.settings.alerts_repeat_time)
        next_alert = self.date_time_str(localtime(next_alert))
        self.email.smtp_write('<tr><td>n&auml;chste Mitteilung (falls aktiv)<td  align="right">{:s}</tr>'
                              .format(next_alert))
        self.email.smtp_write('</table>\n')

    def footer(self):
        """
        Add HTML footer to report.
        """
        self.email.smtp_write('</body>\n')
        self.email.smtp_write('</html>\n')
