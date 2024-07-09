#!/usr/bin/env python3

###############################################################################
# flora.py
# Plant monitoring and irrigation system using Raspberry Pi
#
# - based on data provided by Mi Flora Plant Sensor MQTT Client/Daemon
# - controls water pump for irrigation
# - monitors water tank - two levels, low and empty
# - provides control/status via MQTT
# - sends alerts via SMTP emails
#
# MQTT subscriptions:
#     <base_topic_sensors>/<sensor_name>     (JSON encoded data)
#     <base_topic>/man_report_cmd            (-)
#     <base_topic>/man_irr_cmd               (-)
#     <base_topic>/man_irr_duration_ctrl     (<seconds>)
#     <base_topic>/auto_report_ctrl          (0|1)
#     <base_topic>/auto_irr_ctrl             (0|1)
#     <base_topic/sleep_dis_ctrl             (0|1)
#
# MQTT publications:
#     <base_topic>/man_irr_stat              (0|1)
#     <base_topic>/man_irr_duration_stat     (<seconds>)
#     <base_topic>/auto_report_stat          (0|1)
#     <base_topic>/auto_irr_stat             (0|1)
#     <base_topic>/<sensor_name>             (JSON encoded data)*
#     <base_topic>/<sensor_name>/moisture    (<percent>)§
#     <base_topic>/temperature               (<degC>)+
#     <base_topic>/weather                   (JSON encoded data)+
#     <base_topic>/ubatt                     (<mV>)+
#     <base_topic>/sleep_dis_stat            (0|1)
#
# * only with local Mi Flora (flower care) sensors
# § only with local analog soil moisture sensors
# + optional
#
# created: 02/2020 updated: 05/2021
#
# This program is Copyright (C) 02/2020 Matthias Prinke
# <m.prinke@arcor.de> and covered by GNU's GPL.
# In particular, this program is free software and comes WITHOUT
# ANY WARRANTY.
#
# History:
#
# 20200226 Tank level sensor input working
# 20200302 Config file reading implemented
# 20200304 MQTT client for plant sensor data working
# 20200309 E-mail report implemented, pump control via MQTT message working
# 20200325 Sending e-mail report based on sensor/plant data implemented
# 20200421 Specific irrigation time for automatic/manual mode added
#          MQTT feedback messages for manual irrigation time setting added
#          Handling of sensor time-out added
# 20200428 Added switching auto reporting and auto irrigation on/off via MQTT
# 20200502 Rev. 1.0, Initial release
# 20200504 Added night mode
# 20210105 Fixed manual irrigation
#          Messages were queued while irrigation was already in progress,
#          which led to multiple irrigation cycles where only one was desired.
#          Added message 'man_irrigation_status'
# 20210106 Code cleanup
#          Added tank object as parameter to Pump class constructor -
#          the mapping between pump and tank will never change during run time
# 20210116 Major refactoring and switch to object oriented implementation
#          Functional improvement of E-mail reporting
# 20210117 Split source file into multiple modules
#          Replaced set-/get-methods by properties
# 20210118 Renamed MQTT topics
# 20210202 Changed ConfigParser usage for compatibility with MicroPython
#          Various modifications for MicroPython
# 20210203 Added e-mail reporting with MicroPython
# 20210207 Changed report to send email in smaller chunks
#          due to ESP memory constraints
# 20210208 Replaced config by settings (mostly)
# 20210209 Moved config to settings
# 20210210 Added SSL to MicroPython / uMQTT implementation
# 20210211 Workaround for Out-of-Memory in umail.SMTP()
#          (Only occurs with MQTT over SSL):
#          MQTT client disconnect -> send mail -> MQTT reconnect
# 20210212 Added re-connection after WLAN interruption
#          (not fully working)
# 20210213 uMQTT function calls cluttered with try/except - needs reworking
# 20210315 Added support for analog soil moisture sensors
# 20210316 Added connecting to WLAN access point from list in secrets.py
# 20210317 Modified status report for moisture-only sensor sensors
#          Added support for one-wire temperature sensors
# 20210318 Moved MQTT code to module flora_mqtt
# 20210321 Praparations for retaining state while in deep sleep mode (ESP32)
# 20210323 Implemented deep sleep mode (ESP32)
# 20210324 Improve sleep mode on ESP32 - added auto_report & auto_irrigation
#          to saved state
# 20210329 Fixed running pump by adding MQTT pings (uMQTT)
# 20210508 Added support of MiFlora Bluetooth Low Energy plant sensors
# 20210509 Added support of BME280 temperature/humidity/pressure sensor
# 20210511 Added optional battery voltage measurement
# 20210519 Modified access to tank/pump
#
# ToDo:
# 
# - add handling of multiple pumps (Sensor -> Pump -> Tank)
# - check WLAN reconnection behaviour
# - check if  uMQTT.robust or uMQTT.robust2 is the right choice
# - add Wi-Fi Manager - FAILED due to lack of memory
# - add SSL features for using with uMQTT
# - add daily min/max of sensor values
# - compare light value against daily average
#
###############################################################################


import sys
import os
import json
import binascii
import time
from time import sleep
from ntptime import settime

if sys.implementation.name == "micropython":
    import wifi
    import miflora
    from miflora import Mi_Flora
    import machine
    import ntptime
    from ubluetooth import BLE
    # FIXME move to a module
    from machine import Pin, I2C, SoftI2C, reset
    import bme280
    if sys.platform == "esp32":
        import adc1_cal
else:
    import struct
    import argparse
    import os.path
    import locale
    from colorama import init as colorama_init
    from colorama import Fore, Back, Style

# Flora specific modules
import config as cfg
import sensor as s
import flora_mqtt as mqtt
import tank
import pump
import report
import irrigation
import alert as m_alert
import sensor_power
import moisture
import temperature
from config import DEBUG, MEMINFO, VERBOSITY
from print_line import *
from gpio import *
from garbage_collect import gcollect, meminfo

def save_state(alerts, settings):
    """
    Save state of alerts to Low Power RAM (RTC RAM) which will retain its contents during deep sleep mode

    Parameters:
        alerts (Alert):     list of instances of Alert class
    """
    if sys.platform == "esp32":
        # 5 words per alert, 4 bytes per word + 2 bytes
        buf = bytearray(len(alerts) * 6 * 4 + 2)
        offs = 0
        for a in alerts:
            state = a.state
#            if (VERBOSITY > 1):
#                print_line('save_state(): data = {}'.format(state))
            for item in state:
                for byte in range(4):
                    buf[offs] = item & 0xff
                    offs += 1
                    item = item >> 8
        buf[offs]   = settings.auto_irrigation
        buf[offs+1] = settings.auto_report
        if (DEBUG):
            print_line('save_state(): buf = {}'.format(buf))
        rtc = machine.RTC()
        rtc.memory(buf)


def load_state(alerts, settings):
    """
    Load state of alerts from Low Power RAM (RTC RAM) which will retain its contents during deep sleep mode

    Parameters:
        alerts (Alert):     list of instances of Alert class
    """    
    if (sys.platform == "esp32"):
        rtc = machine.RTC()
        buf = rtc.memory()
        if (DEBUG):
            print_line('load_state(): buf = {}'.format(buf))
        # 6 words per alert, 4 bytes per word
        offs = 0
        state = [0] * 6
        for a in alerts:
            for i in range(6):
                state[i] = (buf[offs+3] << 24) | \
                        (buf[offs+2] << 16) | \
                        (buf[offs+1] <<  8) | \
                        (buf[offs+0])
                offs += 4
#            if (VERBOSITY > 0):
#                print_line('load_state(): data = {}'.format(state))
            a.state = state
        settings.auto_irrigation = buf[offs]
        settings.auto_report     = buf[offs+1]
        print_line('load_state(): auto_irrigation = {} auto_report = {}'.format(settings.auto_irrigation, settings.auto_report))


# Micropython esp8266/esp32
# This code returns the Central European Time (CET) including daylight saving
# Winter (CET) is UTC+1H Summer (CEST) is UTC+2H
# Changes happen last Sundays of March (CEST) and October (CET) at 01:00 UTC
# Ref. formulas : http://www.webexhibits.org/daylightsaving/i.html
#                 Since 1996, valid through 2099
def cettime():
    year = time.localtime()[0]       #get current year
    HHMarch   = time.mktime((year,3 ,(31-(int(5*year/4+4))%7),1,0,0,0,0,0)) #Time of March change to CEST
    HHOctober = time.mktime((year,10,(31-(int(5*year/4+1))%7),1,0,0,0,0,0)) #Time of October change to CET
    now=time.time()
    if now < HHMarch :               # we are before last sunday of march
        cet=time.localtime(now+3600) # CET:  UTC+1H
    elif now < HHOctober :           # we are before last sunday of october
        cet=time.localtime(now+7200) # CEST: UTC+2H
    else:                            # we are after last sunday of october
        cet=time.localtime(now+3600) # CET:  UTC+1H
    return(cet)


def main():
    # Set system clock from NTP server 
    try:
        ntptime.settime()
    except OSError as e:
        wifi.deinit()
        machine.reset()
        
    # Set time to Central European Time (CET) including daylight saving 
    tm = cettime()

    # Set Real Time Clock to CET
    machine.RTC().datetime((tm[0], tm[1], tm[2], tm[6] + 1, tm[3], tm[4], tm[5], 0))

    # Print system time
    print('Time: {}/{:02}/{:02} {:02}:{:02}:{:02}'.format(tm[0], tm[1], tm[2], tm[3], tm[4], tm[5]))

    gcollect()
    if MEMINFO:
        meminfo('__main__ gc')
    
    if sys.implementation.name != "micropython":
        locale.setlocale(locale.LC_ALL, 'de_DE.UTF8')

        # Argparse
        # https://pymotw.com/3/configparser/
        # https://stackoverflow.com/questions/22068050/iterate-over-sections-in-a-config-file
        parser = argparse.ArgumentParser(description=cfg.PROJECT_NAME)
        parser.add_argument('--config_dir',
                            help='set directory where config.ini is located',
                            default=sys.path[0])
        parse_args = parser.parse_args()
        config_dir = parse_args.config_dir
    else:
        config_dir = './'
    
    # Intro
    if sys.implementation.name != "micropython":
        locale.setlocale(locale.LC_ALL, 'de_DE.UTF8')
        colorama_init()
        print(Fore.GREEN + Style.BRIGHT)
        print(cfg.PROJECT_NAME)
        print(cfg.PROJECT_VERSION)
        print('Source:', cfg.PROJECT_URL)
        print(Style.RESET_ALL)
    else:
        print(cfg.PROJECT_NAME)
        print(cfg.PROJECT_VERSION)
        print('Source:', cfg.PROJECT_URL)        

#    if (VERBOSITY > 0):
#        print_line('Platform: {}'.format(sys.platform))

    # Initialize settings
    cfg.settings = cfg.Settings(config_dir, delimiters=('=', ), inline_comment_prefixes=('#'))
    
    if MEMINFO:
        meminfo('Settings')

    # Set BCM pin addressing mode
    GPIO.setmode(GPIO.BCM)
    
    sensor_pwr = sensor_power.SensorPower(cfg.GPIO_SENSOR_POWER)
    
    # Generate tank object (fill level sensors)
    tank.tank = tank.Tank(cfg.GPIO_TANK_SENS_LOW, cfg.GPIO_TANK_SENS_EMPTY)

    # Generate pump object
    pump.pump = pump.Pump(cfg.GPIO_PUMP_POWER, cfg.GPIO_PUMP_STATUS, tank.tank)
    
    # Get list of sensor names from config file
    sensor_list = cfg.settings.mqtt_sensors
    sensor_list = sensor_list.split(',')

    if (sensor_list == []):
        print_line('No sensors found in the [MQTT] section of "config.ini".',
                error=True, sd_notify=True)
        sys.exit(1)

    # Create a dictionary of Sensor objects
    s.sensors = {}
    gcollect()
    
    for sensor in sensor_list:
        s.sensors[sensor] = s.Sensor(sensor, cfg.settings.mqtt_msg_timeout, cfg.settings.sensor_batt_low)
        # check if config file contains a section for this sensor
        if (not(cfg.settings.has_section(sensor))):
            print_line('The configuration file "config.ini" has a sensor named {} in the [MQTT] section,'
                    .format(sensor), error=True, sd_notify=True)
            print_line('but no plant data has provided in a section named accordingly.',
                    error=True, sd_notify=True)
            sys.exit(1)

    if MEMINFO:
        meminfo('Sensor')

    # Options expected (mandatory!) in each sensor-/plant-data section of the config-file
    OPTIONS = [
        'name',
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
        'light_max'
    ]

    # Read all plant data from the section (section name = sensor name)
    for sensor in s.sensors:
        for option in OPTIONS:
            if (not(cfg.settings.has_option(sensor, option))):
                print_line('The configuration file "config.ini" has a section "[' + sensor + ']",',
                        error=True, sd_notify=True)
                print_line('but the key "' + option + '" is missing.',
                        error=True, sd_notify=True)
                sys.exit(1)
        
        s.sensors[sensor].init_plant(
            plant     = cfg.settings.get(sensor, 'name'),
            temp_min  = cfg.settings.getfloat(sensor, 'temp_min'),
            temp_max  = cfg.settings.getfloat(sensor, 'temp_max'),
            cond_min  = cfg.settings.getint(sensor, 'cond_min'),
            cond_max  = cfg.settings.getint(sensor, 'cond_max'),
            moist_min = cfg.settings.getint(sensor, 'moist_min'),
            moist_lo  = cfg.settings.getint(sensor, 'moist_lo'),            
            moist_hi  = cfg.settings.getint(sensor, 'moist_hi'),
            moist_max = cfg.settings.getint(sensor, 'moist_max'),
            light_min = cfg.settings.getint(sensor, 'light_min'),
            light_irr = cfg.settings.getint(sensor, 'light_irr'),
            light_max = cfg.settings.getint(sensor, 'light_max')
        )
        
        if (cfg.settings.sensor_interface == 'ble'):
            if (not(cfg.settings.has_option(sensor, 'address'))):                
                print_line('The configured plant sensor interface is Bluetooth LE,')
                print_line('the configuration file "config.ini" has a section "[' + sensor + ']",',
                            error=True, sd_notify=True)
                print_line('but the mandatory key "address" is missing.',
                            error=True, sd_notify=True)
                sys.exit(1)
            
            addr = cfg.settings.get(sensor, 'address')
            addr = addr.replace(':', '')
            addr = binascii.unhexlify(addr)
            s.sensors[sensor].address = bytes(addr, "utf-8")

        # Remove section from memory allocated by ConfigParser 
        cfg.settings.remove_section(sensor)
        gcollect()
    
    # FIXME moisture_interface
    if (cfg.settings.sensor_interface == 'local'):
        if (len(sensor_list) > len(cfg.MOISTURE_ADC_PINS)):
            print_line('Configured number sensors exceeds number of analog inputs (MOISTURE_ADC_PINS) in config.py',
                    error=True, sd_notify=True)
            sys.exit(1)
            
        moisture_sensors = {}
        for i, sensor in enumerate(sensor_list):
            moisture_sensors[sensor] = moisture.Moisture(cfg.MOISTURE_ADC_PINS[i], cfg.MOISTURE_MIN_VAL, cfg.MOISTURE_MAX_VAL)
            
            
    if MEMINFO: 
        meminfo('Moisture')
    gcollect()
        
    # Initialize irrigation
    irr = irrigation.Irrigation()
    
    if MEMINFO:
        meminfo('Irrigation')
    gcollect()
    
    if MEMINFO:
        meminfo('Pre MQTTClient')
    
    # Init MQTT client
    if sys.implementation.name == "micropython":
        mqtt.MQTTClient.DEBUG = True
        mqtt.mqtt_umqtt_init()
        mqtt.mqtt_client.publish(cfg.settings.base_topic_flora + '/status', "online",
                                 qos=mqtt.lim_qos(2), retain=True)
    else:
        mqtt.mqtt_paho_init(cfg.settings, s.sensors)

    if MEMINFO:    
        meminfo('MQTTClient')
    
    if sys.implementation.name != "micropython":
        # Start MQTT network handler loop
        # (for MicroPython, the MQTT network handler loop
        #  will be called in main ececution loop)
        mqtt_client.loop_start()

        # Notify syslogd that we are up and running
        sd_notifier.notify('READY=1')


    if (cfg.settings.sensor_interface == 'mqtt'):
        # Wait until MQTT data is valid (this may take a while...)
        print_line('Waiting for MQTT sensor data -->',
               console=True, sd_notify=True)
        
        for sensor in s.sensors:
            while (not(s.sensors[sensor].valid)):
                if sys.implementation.name == "micropython":
                    mqtt.mqtt_client.check_msg()
                    mqtt.mqtt_client.ping()
                sleep(1)
            if (VERBOSITY > 1):
                print_line(sensor + ' ready!', console=True, sd_notify=True)

        print_line('<-- Initial reception of MQTT sensor data succeeded.',
                console=True, sd_notify=True)
        

    # Init sensor value alerts
    alerts = []
    alerts.append(m_alert.Alert(cfg.settings, cfg.settings.alerts_w_moisture, 'sensors', s.sensors, 'moist_ul', 'moist_oh', "Moisture_Warning"))
    alerts.append(m_alert.Alert(cfg.settings, cfg.settings.alerts_i_moisture, 'sensors', s.sensors, 'moist_ll', 'moist_hl', "Moisture_Info"))
    
    if (cfg.settings.sensor_interface == 'mqtt'):
        alerts.append(m_alert.Alert(cfg.settings, cfg.settings.alerts_w_battery, 'sensors', s.sensors, 'batt_ul', NONE, "Battery"))
    
    if (cfg.settings.sensor_interface == 'mqtt' or cfg.settings.temperature_sensor):
        alerts.append(m_alert.Alert(cfg.settings, cfg.settings.alerts_w_temperature, 'sensors', s.sensors, 'temp_ul', 'temp_oh', "Temperature"))
    
    if (cfg.settings.sensor_interface == 'mqtt'):
        alerts.append(m_alert.Alert(cfg.settings, cfg.settings.alerts_w_conductivity, 'sensors', s.sensors, 'cond_ul', 'cond_oh', "Conductivity"))
        alerts.append(m_alert.Alert(cfg.settings, cfg.settings.alerts_w_light, 'sensors', s.sensors, 'light_ul', 'light_oh',      "Light"))
    
    # Init system alerts
    if (cfg.settings.sensor_interface == 'mqtt'):
        alerts.append(m_alert.Alert(cfg.settings, cfg.settings.alerts_e_sensor, 'sensors', s.sensors, 'timeout', "Sensor"))
    
    alerts.append(m_alert.Alert(cfg.settings, cfg.settings.alerts_e_pump, 'system', pump.pump, 'error', "Pump"))
    alerts.append(m_alert.Alert(cfg.settings, cfg.settings.alerts_e_tank_low, 'system', tank.tank, 'low', "Tank Low"))
    alerts.append(m_alert.Alert(cfg.settings, cfg.settings.alerts_e_tank_empty, 'system', tank.tank, 'empty', "Tank Empty"))
        
    if MEMINFO:
         meminfo('Alerts')
        
    gcollect()
    
    if (sys.platform == "esp32") and (machine.reset_cause() == machine.DEEPSLEEP_RESET):
        load_state(alerts, cfg.settings)
    
    gcollect()
    
    meminfo('Start Main Loop')

    if (VERBOSITY > 0):     
#        print_line("------------------")
        print_line("Start Main Loop.")
#        print_line("------------------")


    ###############################################################################
    # Main execution loop
    ###############################################################################
    while (True):
        if sys.implementation.name == "micropython":
            # While Eclipse Paho maintains a network handler loop,
            # uMQTT network services have to be handles manually
            mqtt.mqtt_client.check_msg()

        gcollect()
        if (sys.platform == "esp32"):
            sensor_pwr.enable(True)
            sleep(1)
        
        if (cfg.settings.sensor_interface == 'local'):
            for sensor in sensor_list:
                valid, moist_val = moisture_sensors[sensor].moisture
                if (valid):
                    s.sensors[sensor].update_moisture_sensor(moist_val)
                    data = {}
                    data['moisture'] = moist_val
                    json_data = json.dumps(data)
                    mqtt.mqtt_client.publish(cfg.settings.base_topic_flora + '/' + sensor, json_data,
                                             qos = 1, retain=False)
                else:
                    print_line('Moisture sensor "{}" value={} - out of range. Check connection and power settings.'
                               .format(sensor, moisture),
                               error=True, sd_notify=True)

        if (cfg.settings.sensor_interface == 'ble'):
            ble = BLE()
            miflora_ble = Mi_Flora(ble)

            for sensor in s.sensors:
                addr = s.sensors[sensor].address
                print_line('Connecting to MiFlora sensor {}'.format(binascii.hexlify(addr)), error=True, sd_notify=True)
                miflora_ble.gap_connect(miflora.ADDR_TYPE_PUBLIC, addr)
                
                for retries in range(cfg.BLE_MAX_RETRIES):
                    if miflora_ble.wait_for(miflora.S_READ_SENSOR_DONE, cfg.BLE_TIMEOUT):
                        print_line("Battery Level: {}%".format(miflora_ble.battery))
                        #print("Version: {}".format(miflora_ble.version))
                        print_line("Temperature: {}°C Light: {}lx Moisture: {}% Conductivity: {}µS/cm".format(
                            miflora_ble.temp, miflora_ble.light, miflora_ble.moist, miflora_ble.cond)
                        )
                        s.sensors[sensor].update_sensor(miflora_ble.temp, miflora_ble.cond, miflora_ble.moist, miflora_ble.light, miflora_ble.battery)
                        mqtt.mqtt_client.publish(cfg.settings.base_topic_flora + '/' + sensor, s.sensors[sensor].data,
                                 qos = 0, retain=False)

                        break
                    else:
                        print_line("Reading MiFlora failed!")
                
                miflora_ble.disconnect()
                
                if (not(cfg.settings.deep_sleep)):
                    # only need to wait if we are not going to sleep at end of cycle
                    if miflora_ble.wait_for_connection(False, cfg.BLE_TIMEOUT):
                        print_line("MiFlora disconnected.")
                    else:
                        print_line("MiFlora disconnect failed!")
                        miflora_ble._reset()
            del miflora_ble
            del ble
            gcollect()
            
        # FIXME
        if cfg.settings.temperature_sensor:
            temperature_sensor = temperature.Temperature(cfg.GPIO_TEMP_SENS, 0)
            if (temperature_sensor.devices > 0):
                temp = temperature_sensor.temperature
                #s.sensors[sensor].update_temperature_sensor(temperature)
                print_line("DS1820 - Temperature: {}°C".format(temp))
                mqtt.mqtt_client.publish(cfg.settings.base_topic_flora + '/temperature', 
                                     '{:2.1f}'.format(temp), qos = 1, retain=False)
            del temperature_sensor
            gcollect()
        
        # FIXME Move to module
        if cfg.settings.weather_sensor:
            try:
                bus = SoftI2C(scl=Pin(cfg.GPIO_I2C_SCL), sda=Pin(cfg.GPIO_I2C_SDA))
            except OSError as exc:
                print_line('I2C Bus Error! ({})!'.format(exc.args[1]), error=True, console=True, sd_notify=True)
            
            try:
                bme = bme280.BME280(i2c=bus, address=cfg.BME280_ADDR, mode=bme280.BME280_OSAMPLE_1)
            except OSError as exc:
                print_line('Failed to access BME280 sensor at I2C address {}!'.format(hex(cfg.BME280_ADDR)), 
                           error=True, console=True, sd_notify=True)
            else:
                weather_sensor = {}
                weather_sensor['temperature'] = round(bme.temperature(), 1)
                weather_sensor['pressure']    = round(bme.pressure(), 0)
                weather_sensor['humidity']    = round(bme.humidity(), 0)
                print_line("BME280 - Temperature: {}°C Humidity: {:.0f}% Pressure: {:.0f}hPa"
                           .format(weather_sensor['temperature'], weather_sensor['humidity'], weather_sensor['pressure'])
                )
                weather_data = json.dumps(weather_sensor)
                mqtt.mqtt_client.publish(cfg.settings.base_topic_flora + '/weather', weather_data,
                                            qos = 1, retain=False)
        
        gcollect()

        if cfg.settings.battery_voltage:
            ubatt = adc1_cal.ADC1Cal(cfg.UBATT_ADC_PIN, cfg.UBATT_DIV, cfg.VREF, cfg.UBATT_SAMPLES, "ADC1_Calibrated")
            print_line('Battery Voltage: {:4}mV'.format(ubatt.voltage))
            mqtt.mqtt_client.publish(cfg.settings.base_topic_flora + '/ubatt', 
                                     '{}'.format(ubatt.voltage), qos = 1, retain=False)

        alert = False
        for a in alerts:
            alert |= a.check()
        
        gcollect()
        
        # Execute automatic sending of mail reports
        if (False and cfg.settings.auto_report):
            if (alert):
                print_line('Alert triggered.', console=True, sd_notify=True)
                
                # To avoid Out-of-Memory exception in SMTP constructor (using SSL) on ESP32,
                # disconnect MQTT client before sending mail
                if sys.implementation.name == "micropython":
                    if MEMINFO:
                        meminfo('Pre MQTTClient disconnect')
                    mqtt.mqtt_client.disconnect()
                    if MEMINFO:
                        meminfo('MQTTClient disconnect')
                    gcollect()
                    if MEMINFO:
                        meminfo('MQTTClient disconnct gc')
                
                meminfo('Report')
                
                # Send report as mail
                report.Report(cfg.settings, s.sensors, tank.tank, pump.pump)
                
                # Reconnect MQTT client
                if sys.implementation.name == "micropython":
                    gcollect()
                    mqtt.mqtt_umqtt_reconnect()

        # Publish status flags/values
        mqtt.mqtt_client.publish(cfg.settings.base_topic_flora + '/auto_report_stat', str(cfg.settings.auto_report),
                                 qos = mqtt.lim_qos(2), retain=True)
        mqtt.mqtt_client.publish(cfg.settings.base_topic_flora + '/auto_irr_stat', str(cfg.settings.auto_irrigation),
                                 qos = mqtt.lim_qos(2), retain=True)
        mqtt.mqtt_client.publish(cfg.settings.base_topic_flora + '/man_irr_duration_stat', str(cfg.settings.irr_duration_man), 
                                 qos = mqtt.lim_qos(2), retain=True)
        mqtt.mqtt_client.publish(cfg.settings.base_topic_flora + '/man_irr_stat', str(0))
        mqtt.mqtt_client.publish(cfg.settings.base_topic_flora + '/sleep_dis_stat', '0' if cfg.settings.deep_sleep else '1', 
                                 qos = mqtt.lim_qos(2), retain=True)

        # Execute manual irrigation (if requested)
        irr.man_irrigation(cfg.settings, pump.pump)
        
        # Execute automatic irrigation
        if (cfg.settings.auto_irrigation):
            cfg.settings.irr_scheduled = irr.auto_irrigation(cfg.settings, s.sensors, pump.pump)
        
        gcollect()

        if (VERBOSITY > 1):
            for sensor in s.sensors:
                print_line("{:16s} Moisture: {:3d} % Temperature: {:2.1f} °C Conductivity: {:4d} uS/cm Light: {:6d} lx Battery: {:3d} %"
                        .format(sensor,
                        s.sensors[sensor].moist,
                        s.sensors[sensor].temp,
                        s.sensors[sensor].cond,
                        s.sensors[sensor].light,
                        s.sensors[sensor].batt))

        if (cfg.settings.daemon_enabled):
            if (sys.platform == "esp32"):
                sensor_pwr.enable(False)

                if (cfg.settings.deep_sleep):
                    save_state(alerts, cfg.settings)
                    print_line('Entering deep sleep in 5 seconds, will wake up after {} seconds ...'
                            .format(cfg.settings.processing_period))
                    mqtt.mqtt_client.publish(cfg.settings.base_topic_flora + '/status', "offline",
                                            qos = mqtt.lim_qos(2), retain=True)
                    sleep(2)
                    mqtt.mqtt_client.disconnect()
                    sleep(3)
                    sleep_duration = cfg.settings.processing_period
                    del sensor_pwr
                    del tank.tank
                    del pump.pump
                    try:
                        for obj in moisture_sensors:
                            del obj
                    except NameError as exc:
                        pass
                    for obj in s.sensors:
                        del obj
                    for obj in alerts:
                        del obj
                    del mqtt.mqtt_client
                    del cfg.settings
                    wifi.deinit()
                    machine.deepsleep(sleep_duration * 1000)
                    while True:
                        # Thou shall not pass!
                        pass
                
            if (VERBOSITY > 1):
                print_line('Sleeping ({} seconds) ...'.format(cfg.settings.processing_period))

            # Sleep for <processing_period> seconds
            count = 0
            for step in range(cfg.settings.processing_period):
                # Quit sleeping if flag has been set (asynchronously) in 'mqtt_man_irr_cmd'
                # message callback function
                if (pump.pump.busy):
                    break
                
                if sys.implementation.name == "micropython":
                    # While Eclipse Paho maintains a network handler loop,
                    # uMQTT network services have to be handles manually
                    mqtt.mqtt_client.check_msg()
                        
                    if (count == cfg.settings.mqtt_keepalive):
                        count = 0
                        mqtt.mqtt_client.ping()
                    else:
                        count += 1
                sleep(1)
        else:
            print_line('Finished in non-daemon-mode', sd_notify=True)
            mqtt.mqtt_client.disconnect()
            break
  

###############################################################################
# Init
###############################################################################

if __name__ == '__main__':
    if MEMINFO:
        meminfo('Boot begin')

    wifi.init()

    if wifi.connectWiFi(wifi.station):
        print('Network config:', wifi.station.ifconfig())
        print("WLAN connection ready!")
    else:
        print("Something went wrong! Let's reboot and try again after {} seconds.".format(config.WLAN_RETRY_DELAY))
        sleep(config.WLAN_RETRY_DELAY)
        reset()

    if MEMINFO:
        meminfo('Boot finished')

    gc.enable()
    #print("gc.mem_free(): {}; gc.mem_alloc(): {}".format(gc.mem_free(), gc.mem_alloc()))
    #gc.mem_free(): 23344; gc.mem_alloc(): 87824
    gc.threshold(gc.mem_free() // 2 + gc.mem_alloc())

    if MEMINFO:
        meminfo('__main__')
    
    main()
    
