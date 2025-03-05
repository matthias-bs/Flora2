#!/usr/bin/env python3

###############################################################################
# main.py
# Plant monitoring and irrigation system using Raspberry Pi / Espressif ESP32
#
# - based on data provided by Mi Flora Plant Sensor MQTT Client/Daemon
# - controls water pumps for irrigation
# - monitors water tank - two levels, low and empty
# - provides control/status via MQTT
# - sends alerts via SMTP emails
#
# MQTT subscriptions:
#     <base_topic_sensors>/<sensor_name>     (JSON encoded data)
#     <base_topic>/man_report_cmd            (-)
#     <base_topic>/man_irr_cmd               (1|2)
#     <base_topic>/man_irr_duration_ctrl     (<seconds>)
#     <base_topic>/auto_report_ctrl          (0|1)
#     <base_topic>/auto_irr_ctrl             (0|1)
#     <base_topic/sleep_dis_ctrl             (0|1)
#
# MQTT publications:
#     <base_topic>/status                    (online|offline|idle|dead$)
#     <base_topic>/man_irr_stat              (0|1)
#     <base_topic>/man_irr_duration_stat     (<seconds>)
#     <base_topic>/auto_report_stat          (0|1)
#     <base_topic>/auto_irr_stat             (0|1)
#     <base_topic>/tank                      (0|1|2)
#     <base_topic>/<sensor_name>             (JSON encoded data)*
#     <base_topic>/<sensor_name>/moisture    (<percent>)§
#     <base_topic>/temperature               (<degC>)+
#     <base_topic>/weather                   (JSON encoded data)+
#     <base_topic>/ubatt                     (<mV>)+
#     <base_topic>/sleep_dis_stat            (0|1)
#
# $ via LWT
# * only with local Mi Flora (flower care) sensors
# § only with local analog soil moisture sensors
# + optional
#
# created: 02/2020 updated: 07/2021
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
# 20210321 Preparations for retaining state while in deep sleep mode (ESP32)
# 20210323 Implemented deep sleep mode (ESP32)
# 20210324 Improve sleep mode on ESP32 - added auto_report & auto_irrigation
#          to saved state
# 20210329 Fixed running pump by adding MQTT pings (uMQTT)
# 20210508 Added support of MiFlora Bluetooth Low Energy plant sensors
# 20210509 Added support of BME280 temperature/humidity/pressure sensor
# 20210511 Added optional battery voltage measurement
# 20210519 Modified access to tank/pump
# 20210521 Code restructured
#          Changed uMQTT implementation to micropython-umqtt.robust2
#          (https://github.com/fizista/micropython-umqtt.robust2)
# 20210531 Modified MQTT protocol handling
#          Added status message
# 20210608 Added control of 2nd pump
# 20210609 Modified load_state()/save_state() and added items
# 20210622 Updated adc1_cal, improved analog moisture sensor data evaluation
#          Added BLE exception handling
# 20210711 Fixed sending of MQTT status messages and handling of 
#          boolean fallback values
#          Fixed auto irrigation
# 20240709 Updated include statements for MicroPython v1.23.0 compatibility 
#          Prevent sleep mode if battery voltage input is disconnected
# 20250305 Removed alert, replaced report email by MQTT message
#          modified string formatting, code improvements
#
# ToDo:
# 
# - fix MQTT over TLS
# - add daily min/max of sensor values
# - compare light value against daily average
#
# Notes:
#
# - adding Wi-Fi Manager failed due to lack of memory
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
    import uerrno
    from bluetooth import BLE
    from machine import reset
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
from config import DEBUG, MEMINFO, VERBOSITY
import flora_mqtt as m_mqtt
from garbage_collect import gcollect, meminfo
from gpio import *
import irrigation as m_irrigation
import moisture as m_moisture
from print_line import *
import pump as m_pump
import report as m_report
import sensor as s
import sensor_power as m_sensor_power
import tank as m_tank
import temperature as m_temperature
import weather as m_weather

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
    print_line(f'NTP Time: {tm[0]}/{tm[1]:02}/{tm[2]:02} {tm[3]:02}:{tm[4]:02}:{tm[5]:02}')

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
        print(cfg.PROJECT_BUILD)
        print('Source:', cfg.PROJECT_URL)
        print(Style.RESET_ALL)
    else:
        print(cfg.PROJECT_NAME)
        print(cfg.PROJECT_VERSION)
        print(cfg.PROJECT_BUILD)
        print('Source:', cfg.PROJECT_URL)        

    # Initialize settings
    cfg.settings = cfg.Settings(config_dir, delimiters=('=', ), inline_comment_prefixes=('#'))
    
    if cfg.settings.battery_voltage:
        ubatt = adc1_cal.ADC1Cal(machine.Pin(cfg.UBATT_ADC_PIN), cfg.UBATT_DIV, cfg.VREF, cfg.UBATT_SAMPLES, "ADC1_Calibrated")
        ubatt.atten(machine.ADC.ATTN_6DB)
        print_line(f'Battery Voltage: {ubatt.voltage:4}mV')
        
        # First energy saving level: switch to processing_period2
        if (ubatt.voltage < cfg.settings.battery_weak):
            sleep_duration = cfg.settings.processing_period2
        else:
            sleep_duration = cfg.settings.processing_period
        
        # Second energy saving level: immediately go to sleep
        if (ubatt.voltage < cfg.settings.battery_low) and (ubatt.voltage > 1000):
            del ubatt    
            del cfg.settings
            wifi.deinit()
            print_line('Low voltage - entering deep sleep')
            machine.deepsleep(sleep_duration * 1000)
            while True:
                 # Thou shall not pass!
                 pass
      
#    if MEMINFO:
#    meminfo('Settings')

    # Set BCM pin addressing mode
    GPIO.setmode(GPIO.BCM)

    # Sensor power control object
    sensor_power = m_sensor_power.SensorPower(cfg.GPIO_SENSOR_POWER)
    
    # Tank object (fill level sensors)
    m_tank.tank = m_tank.Tank(cfg.GPIO_TANK_SENS_LOW, cfg.GPIO_TANK_SENS_EMPTY)

    # Pump objects
    for i in range(2):
        m_pump.pumps[i] = m_pump.Pump(cfg.GPIO_PUMP_POWER[i], cfg.GPIO_PUMP_STATUS[i], m_tank.tank)


    # Get list of sensor names from config file
    sensor_list = cfg.settings.plant_sensors
    sensor_list = sensor_list.split(',')

    if (sensor_list == []):
        print_line('No sensors found in the [Sensors] section of "config.ini".',
                error=True, sd_notify=True)
        sys.exit(1)

    # Create a dictionary of Sensor objects
    s.sensors = {}
    gcollect()
    
    for sensor in sensor_list:
        s.sensors[sensor] = s.Sensor(sensor, cfg.settings.mqtt_msg_timeout, cfg.settings.sensor_batt_low)
        # check if config file contains a section for this sensor
        if (not(cfg.settings.cp.has_section(sensor))):
            print_line(f'The configuration file "config.ini" has a sensor named {sensor} in the [Sensors] section,',
                       error=True, sd_notify=True)
            print_line('but no plant data has been provided in a section named accordingly.',
                    error=True, sd_notify=True)
            sys.exit(1)

#    if MEMINFO:
#        meminfo('Sensor')

    # Options expected (mandatory!) in each sensor-/plant-data section of the config-file
    # Read all plant data from the section (section name = sensor name)
    for sensor in s.sensors:
        if s.config_error(sensor):
            sys.exit(1)
        
        s.sensors[sensor].init_plant()
        
        if (cfg.settings.sensor_interface == 'ble'):            
            addr = cfg.settings.cp.get(sensor, 'address')
            addr = addr.replace(':', '')
            addr = binascii.unhexlify(addr)
            s.sensors[sensor].address = bytes(addr, "utf-8")

        # Remove section from memory allocated by ConfigParser 
        cfg.settings.cp.remove_section(sensor)
    del cfg.settings.cp
    gcollect()
    
    # Local (analog) moisture sensor interface
    if (cfg.settings.sensor_interface == 'local'):
        if (len(sensor_list) > len(cfg.MOISTURE_ADC_PINS)):
            print_line('Configured number sensors exceeds number of analog inputs (MOISTURE_ADC_PINS) in config.py',
                    error=True, sd_notify=True)
            sys.exit(1)
            
        moisture = {}
        for i, sensor in enumerate(sensor_list):
            moisture[sensor] = m_moisture.Moisture(cfg.MOISTURE_ADC_PINS[i], cfg.MOISTURE_MIN_VAL, cfg.MOISTURE_MAX_VAL)
            
    gcollect()
    
    # Init MQTT client
#    if sys.implementation.name == "micropython":
    m_mqtt.MQTTClient.DEBUG = True
    m_mqtt.MQTTClient.MSG_QUEUE_MAX = 1
    m_mqtt.mqtt_umqtt_init()
#    else:
#        m_mqtt.mqtt_paho_init(cfg.settings, s.sensors)

    # Mark2 MQTT init done
    #pin_mark.value(1)
    
    m_mqtt.mqtt_client.publish(cfg.settings.base_topic_flora + '/status', "online",
                               qos=1, retain=True)

#    if MEMINFO:    
#        meminfo('MQTTClient')

    # Initialize irrigation
    irrigation = m_irrigation.Irrigation()
    
    if sys.implementation.name != "micropython":
        # Start MQTT network handler loop
        # (for MicroPython, the MQTT network handler loop
        #  will be called in main ececution loop)
        m_mqtt.mqtt_client.loop_start()

        # Notify syslogd that we are up and running
        sd_notifier.notify('READY=1')


    if (cfg.settings.sensor_interface == 'mqtt'):
        # Wait until MQTT data is valid (this may take a while...)
        print_line('Waiting for MQTT sensor data -->', sd_notify=True)
        
        for sensor in s.sensors:
            while (not(s.sensors[sensor].valid)):
                if sys.implementation.name == "micropython":
                    m_mqtt.mqtt_client.check_msg()
                    m_mqtt.mqtt_client.ping()
                sleep(1)
            if (VERBOSITY > 1):
                print_line(sensor + ' ready!', sd_notify=True)

        print_line('<-- Initial reception of MQTT sensor data succeeded.', sd_notify=True)
    
    meminfo('Start Main Loop')

    if (VERBOSITY > 0):     
        print_line("Start Main Loop.")

    ###############################################################################
    # Main execution loop
    ###############################################################################
    while (True):
        # Mark3 Main Loop
        # pin_mark.value(0)
        m_mqtt.mqtt_client.publish(cfg.settings.base_topic_flora + '/status', "online",
                                   qos=1, retain=True)
        if sys.implementation.name == "micropython":
            gcollect()
            # BEGIN FIXME
            # Note: Something is quite different/wrong with SSL sockets. For now,
            #       we just cross fingers that our connection is good...
            # At this point in the code you must consider how to handle
            # connection errors.  And how often to resume the connection.
            if cfg.settings.mqtt_tls == False and m_mqtt.mqtt_client.is_conn_issue():
                if m_mqtt.mqtt_client.is_conn_issue():
                    # If the connection is successful, the is_conn_issue
                    # method will not return a connection error.
                    m_mqtt.mqtt_client.reconnect()
                else:
                    m_mqtt.mqtt_client.resubscribe()
            m_mqtt.mqtt_client.publish(cfg.settings.base_topic_flora + '/status', "online",
                                       qos=1, retain=True)
 
            for _ in range(cfg.MQTT_MAX_CYCLES):
                # While Eclipse Paho maintains a network handler loop,
                # uMQTT network services have to be handled manually
                m_mqtt.mqtt_client.check_msg()
                m_mqtt.mqtt_client.send_queue()
                time.sleep_ms(500)
            # END FIXME

        if (sys.platform == "esp32"):
            sensor_power.enable(True)
            sleep(1)
        
        if (cfg.settings.sensor_interface == 'local'):
            for sensor in sensor_list:
                valid, moist_val = moisture[sensor].moisture
                if (valid):
                    s.sensors[sensor].update_moisture_sensor(moist_val)
                    data = {}
                    data['moisture'] = moist_val
                    json_data = json.dumps(data)
                    m_mqtt.mqtt_client.publish(cfg.settings.base_topic_flora + '/' + sensor, json_data,
                                               qos = 1, retain=cfg.MQTT_DATA_RETAIN)
                    print_line(f"{sensor} - Moisture: {moist_val}%")
                else:
                    print_line(f'Moisture sensor "{sensor}" value={moist_val} - out of range. Check connection and power settings.',
                               error=True, sd_notify=True)
        
        # Mark4 BLE start
        # pin_mark.value(1)
        if (cfg.settings.sensor_interface == 'ble'):
            try:
                ble = BLE()
                miflora_ble = Mi_Flora(ble)
            except OSError as exc:
                print_line(f'Bluetooth LE exception: {uerrno.errorcode[exc.errno]}', error=True, sd_notify=True)
                print_line('Cannot access MiFlora sensor(s).')
            else:
                for sensor in s.sensors:
                    addr = s.sensors[sensor].address
                    print_line(f'Connecting to MiFlora sensor {binascii.hexlify(addr)}', sd_notify=True)
                    
                    for _ in range(cfg.BLE_MAX_RETRIES):
                        miflora_ble.gap_connect(miflora.ADDR_TYPE_PUBLIC, addr)
                        
                        if miflora_ble.wait_for(miflora.S_READ_SENSOR_DONE, cfg.BLE_TIMEOUT):
                            print_line(f"Battery Level: {miflora_ble.battery}%")
                            #print(f"Version: {miflora_ble.version}")
                            print_line(f"Temperature: {miflora_ble.temp}°C Light: {miflora_ble.light}lx " + \
                                       f"Moisture: {miflora_ble.moist}% Conductivity: {miflora_ble.cond}µS/cm")
                            s.sensors[sensor].update_sensor(miflora_ble.temp, miflora_ble.cond, miflora_ble.moist, miflora_ble.light, miflora_ble.battery)
                            m_mqtt.mqtt_client.publish(cfg.settings.base_topic_flora + '/' + sensor, s.sensors[sensor].data,
                                                    qos = 1, retain=cfg.MQTT_DATA_RETAIN)
                            break
                        else:
                            print_line("Reading MiFlora failed!")
                    
                    miflora_ble.disconnect()
                    if miflora_ble.wait_for_connection(False, cfg.BLE_TIMEOUT):
                        print_line("MiFlora disconnected.")
                    else:
                        print_line("MiFlora disconnect failed!")
                        miflora_ble._reset()
                del miflora_ble
            del ble
            gcollect()
            
        # Mark5 BLE end
        #pin_mark.value(0)
        
        # FIXME
        if cfg.settings.temperature_sensor:
            temperature = m_temperature.Temperature(cfg.GPIO_TEMP_SENS)
            if (temperature.devices > 0):
                temp = temperature.temperature()
                #temperature.show_devices()
                if (cfg.settings.sensor_interface == 'local'):
                    for sensor in s.sensors:
                        s.sensors[sensor].update_temperature_sensor(temp)
                print_line(f"DS1820 - Temperature: {temp}°C")
                m_mqtt.mqtt_client.publish(cfg.settings.base_topic_flora + '/temperature', 
                                         f'{temp:2.1f}', qos = 1, retain=cfg.MQTT_DATA_RETAIN)
            del temperature
            gcollect()
        
        # FIXME 
        if cfg.settings.weather_sensor:
            valid, weather = m_weather.weather_data()
            if (valid):
                weather_data = json.dumps(weather)
                m_mqtt.mqtt_client.publish(cfg.settings.base_topic_flora + '/weather', weather_data,
                                         qos = 1, retain=cfg.MQTT_DATA_RETAIN)

        if cfg.settings.battery_voltage:
            ubatt = adc1_cal.ADC1Cal(machine.Pin(cfg.UBATT_ADC_PIN), cfg.UBATT_DIV, cfg.VREF, cfg.UBATT_SAMPLES, "ADC1_Calibrated")
            ubatt.atten(machine.ADC.ATTN_6DB)
            print_line(f'Battery Voltage: {ubatt.voltage:4}mV')
            m_mqtt.mqtt_client.publish(cfg.settings.base_topic_flora + '/ubatt', 
                                     f'{ubatt.voltage}', qos = 1, retain=cfg.MQTT_DATA_RETAIN)
        
        gcollect()
        meminfo('Report')
            
        # Send system settings & status via MQTT
        report = m_report.Report()
        system = report.gen_report()
        del report

        m_mqtt.mqtt_client.publish(cfg.settings.base_topic_flora + '/system', system, qos = 1, retain=True)

        # Publish status flags/values
        m_mqtt.mqtt_client.publish(cfg.settings.base_topic_flora + '/auto_report_stat', '1' if cfg.settings.auto_report else '0',
                                   qos = 1, retain=True)
        m_mqtt.mqtt_client.publish(cfg.settings.base_topic_flora + '/auto_irr_stat', '1' if cfg.settings.auto_irrigation else '0',
                                   qos = 1, retain=True)
        m_mqtt.mqtt_client.publish(cfg.settings.base_topic_flora + '/man_irr_duration_stat', str(cfg.settings.irr_duration_man), 
                                   qos = 1, retain=True)
        m_mqtt.mqtt_client.publish(cfg.settings.base_topic_flora + '/tank', str(m_tank.tank.status), 
                                   qos = 1, retain=True)
        m_mqtt.mqtt_client.publish(cfg.settings.base_topic_flora + '/sleep_dis_stat', '0' if cfg.settings.deep_sleep else '1', 
                                   qos = 1, retain=True)
       
        # Execute manual irrigation (if requested)
        irrigation.man_irrigation()
        
        m_mqtt.mqtt_client.publish(cfg.settings.base_topic_flora + '/man_irr_stat', '0', qos = 1)

        # Execute automatic irrigation
        if (cfg.settings.auto_irrigation):
            cfg.settings.irr_scheduled = irrigation.auto_irrigation()
        
        gcollect()

        if sys.implementation.name == "micropython":
            for _ in range(cfg.MQTT_MAX_CYCLES):
                # While Eclipse Paho maintains a network handler loop,
                # uMQTT network services have to be handles manually
                m_mqtt.mqtt_client.check_msg()
                m_mqtt.mqtt_client.send_queue()
                time.sleep_ms(500)

        if (VERBOSITY > 1):
            for sensor in s.sensors:
                print_line(f"{sensor:16s} Moisture: {s.sensors[sensor].moist:3d} % Temperature: {s.sensors[sensor].temp:2.1f} " +\
                           f"°C Conductivity: {s.sensors[sensor].cond:4d} uS/cm Light: {s.sensors[sensor].light:6d} " + \
                           f"lx Battery: {s.sensors[sensor].batt:3d} %")

        if (cfg.settings.daemon_enabled):
            if (sys.platform == "esp32"):
                sensor_power.enable(False)

                # Prevent deep sleep if battery voltage input is disconnected
                # to simplify debugging/flashing 
                if (cfg.settings.deep_sleep and ubatt.voltage > 1000):
                    save_state(alerts)
                    print_line(f'Entering deep sleep in 5 seconds, will wake up after {cfg.settings.processing_period} seconds ...')
                    m_mqtt.mqtt_client.publish(cfg.settings.base_topic_flora + '/status', "offline",
                                            qos = 1, retain=True)
                    sleep(2)
                    m_mqtt.mqtt_client.check_msg()
                    m_mqtt.mqtt_client.send_queue()
                    m_mqtt.mqtt_client.disconnect()
                    sleep(3)
                    del sensor_power
                    del m_tank.tank
                    del m_pump.pumps
                    try:
                        for obj in moisture:
                            del obj
                    except NameError as exc:
                        pass
                    for obj in s.sensors:
                        del obj
                    for obj in alerts:
                        del obj
                    del m_mqtt.mqtt_client
                    del cfg.settings
                    wifi.deinit()
                    #pin_mark.value(0)
                    machine.deepsleep(sleep_duration * 1000)
                    while True:
                        # Thou shall not pass!
                        pass
                
            if (VERBOSITY > 0):
                print_line(f'Standby ({cfg.settings.processing_period} seconds) ...')

            m_mqtt.mqtt_client.publish(cfg.settings.base_topic_flora + '/status', "idle",
                                       qos = 1, retain=True)
            m_mqtt.mqtt_client.send_queue()

            # Sleep for <processing_period> seconds
            count = 0
            for _ in range(cfg.settings.processing_period):
                # Quit sleeping if flag has been set (asynchronously) in 'mqtt_man_irr_cmd'
                # message callback function
                if (m_pump.pumps[0].busy or m_pump.pumps[1].busy):
                    break
                
                if sys.implementation.name == "micropython":
                    # While Eclipse Paho maintains a network handler loop,
                    # uMQTT network services have to be handles manually
                    m_mqtt.mqtt_client.check_msg()
                    if (count == cfg.settings.mqtt_keepalive):
                        count = 0
                        m_mqtt.mqtt_client.ping()
                    else:
                        count += 1
                sleep(1)
        else:
            m_mqtt.mqtt_client.publish(cfg.settings.base_topic_flora + '/status', "offline",
                                       qos = 1, retain=True)
            m_mqtt.mqtt_client.send_queue()
            print_line('Finished in non-daemon-mode', sd_notify=True)
            m_mqtt.mqtt_client.disconnect()
            break
  

###############################################################################
# Init
###############################################################################

if __name__ == '__main__':
    #pin_mark = machine.Pin(0, machine.Pin.OUT, value = 1)
    
    if MEMINFO:
        meminfo('Boot begin')

    wifi.init()

    if wifi.connectWiFi(wifi.station):
        print_line("WiFi connection ready!", error=True)
        print_line(f'Network config: {wifi.station.ifconfig()}')
    else:
        print_line(f"Cannot connect to WiFi! Rebooting in {cfg.WLAN_RETRY_DELAY} seconds.")
        sleep(cfg.WLAN_RETRY_DELAY)
        reset()
    
    # Mark1 WIFI on
    #pin_mark.value(0)
    
    if MEMINFO:
        meminfo('Boot finished')

    gc.enable()
    #print(f"gc.mem_free(): {gc.mem_free()}; gc.mem_alloc(): {gc.mem_alloc()}")
    #gc.mem_free(): 23344; gc.mem_alloc(): 87824
    gc.threshold(gc.mem_free() // 2 + gc.mem_alloc())

    if MEMINFO:
        meminfo('__main__')
    
    main()
    
