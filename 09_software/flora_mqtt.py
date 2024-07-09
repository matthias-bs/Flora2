###############################################################################
# flora.py
#
# This module provides the flora MQTT functions
#
# The module contains code for two different MQTT client implementations -
# - Eclipse Paho MQTT client
#   https://www.eclipse.org/paho/index.php?page=clients/python/index.php
# - uMQTT MicroPython MQTT client
#   https://github.com/micropython/micropython-lib/tree/master/umqtt.robust
#
# created: 03/2021 updated: 05/2021
#
# This program is Copyright (C) 03/2021 Matthias Prinke
# <m.prinke@arcor.de> and covered by GNU's GPL.
# In particular, this program is free software and comes WITHOUT
# ANY WARRANTY.
#
# History:
#
# 20210318 Separated from flora.py
# 20210509 Added description
# 20210519 Fixed access to tank/pump
#          Added "Last Will"
#
# ToDo:
# - 
#
###############################################################################

import sys
import os
import json
import tank
import pump

if sys.implementation.name == "micropython":
    import ussl
    from umqtt.robust2 import MQTTClient
    import machine
    import ubinascii
else:
    import ssl
    import paho.mqtt.client as mqtt

if sys.platform == "esp32":
    import wifi

import config as cfg
import sensor as s
import report as r
from time import sleep
from config import DEBUG, VERBOSITY, PUMP_BUSY_MAN
from print_line import *
from garbage_collect import gcollect





##############################################################################
# Global variables
##############################################################################
mqtt_client = None

#############################################################################################
# Restart
#############################################################################################
def restart():
    if sys.platform == "esp32":
        print_line('Network or MQTT handler error! Restarting...',
                console=True, sd_notify=True)
        sleep(10)
        machine.reset()
    else:
        print_line('Network or MQTT handler error! Giving up...',
                console=True, sd_notify=True)
        os._exit(1)

def lim_qos(qos):
    if (sys.implementation.name == "micropython") and (qos==2):
        return 1
    else:
        return qos

#############################################################################################
# MQTT - uMQTT (MicroPython) Setup and Tweaks
#############################################################################################

class MQTTMessage:
    """
    uMQTT Wrapper for compatibility with Eclipse Paho 

    Attributes:
        topic   (string): MQTT topic
        payload (bytes):  MQTT message payload
    """
    def __init__(self, topic, msg):
        self.topic = topic
        self.payload = msg


#class MQTTClient(robust.MQTTClient):
#    def log(self, in_reconnect, e, where='-'):
#        if self.DEBUG:
#            if in_reconnect:
#                #print("mqtt {} reconnect: {}".format(where, uerrno.errorcode[e]))
#                print("mqtt {} reconnect: {}".format(where, e.args[0]))
#            else:
#                #print("mqtt {}: {}".format(where, uerrno.errorcode[e]))
#                print("mqtt {}: {}".format(where, e.args[0]))
#           
#    def reconnect(self):
#        global mqtt_client
#       
#        i = 0
#        clean_session = False
#        while 1:
#            if sys.platform == "esp32":
#                # While a full-blown OS will (hopefully) handle reconnecting after WLAN drop,
#                # this has to be handled by the application on ESP32.
#                if not wifi.station.isconnected():
#                    if (VERBOSITY > 0):
#                        print_line('WLAN connection lost, trying to reconnect -->',
#                                    console=True, sd_notify=False)
#                    
#                    # Connect to WLAN
#                    try:
#                        wifi.connectWiFi(wifi.station)
#                    except OSError as e:
#                        restart()
#                    
#                    while not wifi.station.isconnected():
#                        sleep(cfg.settings.processing_period)
#                        if (VERBOSITY > 0):
#                            print_line('...waiting for WLAN...', console=True, sd_notify=False)
#                    
#                    if (VERBOSITY > 0):
#                        print_line('<-- WLAN connection ready!', console=True, sd_notify=False)
#            
#            try:
#                print_line('Trying to re-initialize MQTT connection -->')
#                rc = super().connect(clean_session)
#                mqtt_client = mqtt_umqtt_init()
#                print_line('<-- MQTT connection re-established', console=True, sd_notify=True)
#                return rc
#            except OSError as e:
#                self.log(True, e, 'reconnect()')
#                i += 1
#                self.delay(i)
#                clean_session = True
#                if i == cfg.WLAN_MAX_RETRIES:
#                    restart()
#                
#    def connect(self, clean_session=True):
#        while (1):
#           try:
#                return super().connect(clean_session)
#            except OSError as e:
#                self.log(False, e, 'connect()')
#                
                
#    def ping(self):
        #while 1:
            #try:
                #return super().ping()
            #except OSError as e:
                #self.log(False, e, 'ping()')
            #self.reconnect()

def mqtt_umqtt_init():
    """
    Init MQTT client and connect to MQTT broker

    Parameters:
        settings (Settings): Settings instance
        
    Returns:
        MQTT client instance
    """
    #FIXME SSL is basically working, but certificates/keys are not used yet 
    # In order to fix this, the following steps have to be considered_
    # - convert keyfile/certificates to (binary) DER-format
    #   (the textual PEM-format is used more commonly)
    # - the files must be read into variables in binary mode:
    #   if settings.mqtt_keyfile:
    #        with open(settings.mqtt_keyfile, 'rb') as f:
    #            key_data = f.read()
    # - the dictionary ssl_params must be passed in the following manner:
    #   client = MQTTClient(client_id='esp32vroom', server=mqtt_server, port=8883, keepalive=10000, ssl=True, 
    #                       ssl_params={"key":privkey,"cert":certpem,"server_side":False})
    # - ssl_params is passed to ussl.wrap_sockets; the following parameters are available:
    #   keyfile=None, certfile=None, server_side=False,
    #   cert_reqs=CERT_NONE, *, ca_certs=None, server_hostname=None
    # - parameters after '*' must be named
    #
    # A more or less complete discussion can be found here:
    # https://forum.micropython.org/viewtopic.php?f=2&t=5166

    global mqtt_client
    
    if sys.implementation.name == "micropython":
        UNIQUE_ID = ubinascii.hexlify(machine.unique_id()).decode("ascii")
    else:
        UNIQUE_ID = ""
    
    # MQTT client initialization
    mqtt_client = MQTTClient(client_id=(cfg.settings.base_topic_flora+UNIQUE_ID),
                            server=cfg.settings.mqtt_server,
                            port=cfg.settings.mqtt_port,
                            user=cfg.settings.mqtt_user,
                            password=cfg.settings.mqtt_password,
                            keepalive=cfg.settings.mqtt_keepalive,
                            ssl=cfg.settings.mqtt_tls
    )

    mqtt_client.set_last_will(cfg.settings.base_topic_flora + '/status', "dead", qos=lim_qos(2), retain=True)
        
    print_line('Connecting to MQTT broker -->')
    rc = mqtt_client.connect(clean_session=True)
    
    #if rc == 0:
    print_line('<-- MQTT connection established', console=True, sd_notify=True)
    #else:
    #    print_line('Connection error with result code {}'.format(rc), error=True)
        
        #kill main thread
    #    os._exit(1)
    
    # Set up MQTT message subscription and handlers
    #mqtt_setup_messages(mqtt_client, settings, sensors)
    mqtt_setup_messages()
    
    return mqtt_client

def mqtt_umqtt_cb(topic, msg):
    """
    uMQTT sub message callback
    
    Uses global vars <cfg.settings> and <mqtt_client>!!!

    Parameters:
        topic (bytes):  MQTT message topic
        msg (bytes):    MQTT message payload
    """
    # Convert topic from bytes to string
    topic = topic.decode('utf-8')
    
    if (VERBOSITY > 1):
        print_line("uMQTT message handler topic '{}' with msg '{}' received.".format(topic, msg),
                   console=True, sd_notify=True)
    
    userdata = None
    if (topic == cfg.settings.base_topic_flora + '/man_report_cmd'):
        mqtt_man_report_cmd(mqtt_client, userdata, msg=MQTTMessage(topic, msg))
    elif (topic == cfg.settings.base_topic_flora + '/man_irr_cmd'):
        mqtt_man_irr_cmd(mqtt_client, userdata, msg=MQTTMessage(topic, msg))
    elif (topic == cfg.settings.base_topic_flora + '/man_irr_duration_ctrl'):
        mqtt_man_irr_duration_ctrl(mqtt_client, userdata, msg=MQTTMessage(topic, msg))
    elif (topic == cfg.settings.base_topic_flora + '/auto_report_ctrl'):
        mqtt_auto_report_ctrl(mqtt_client, userdata, msg=MQTTMessage(topic, msg))
    elif (topic == cfg.settings.base_topic_flora + '/auto_irr_ctrl'):
        mqtt_auto_irr_ctrl(mqtt_client, userdata, msg=MQTTMessage(topic, msg))
    elif (topic == cfg.settings.base_topic_flora + '/sleep_dis_ctrl'):
        mqtt_sleep_dis_ctrl(mqtt_client, userdata, msg=MQTTMessage(topic, msg))
    else:
        mqtt_on_message(mqtt_client, userdata, msg=MQTTMessage(topic, msg))


def mqtt_umqtt_reconnect():
    
    print_line('Re-connecting to MQTT broker -->')
    rc = mqtt_client.connect(clean_session=True)

    if rc == 0:
        print_line('<-- MQTT connection re-established', console=True, sd_notify=True)
    else:
        print_line('Connection error with result code {}'.format(rc), error=True)
        
        #kill main thread
        os._exit(1)
    
    # Set up MQTT message subscription and handlers
    # Only needed if MQTT broker is configured as non-persistent
    #mqtt_setup_messages(mqtt_client, settings, sensors)
    mqtt_setup_messages()


#############################################################################################
# MQTT - Eclipse Paho Setup
#############################################################################################
#if sys.implementation.name != "micropython":
def mqtt_paho_init():
    """
    Init MQTT client and connect to MQTT broker

    Parameters:
        settings (Settings): Settings instance 
    """
    global mqtt_client
    
    # MQTT client initialization (client ID is generated randomly)
    mqtt_client = mqtt.Client()
    mqtt_client.on_connect = mqtt_on_connect

    if cfg.settings.mqtt_tls:
    # According to the docs, setting PROTOCOL_SSLv23 "Selects the highest protocol version
    # that both the client and server support. Despite the name, this option can select
    # 'TLS' protocols as well as 'SSL'" - so this seems like a resonable default
        mqtt_client.tls_set(
            ca_certs = cfg.settings.mqtt_ca_cert,
            keyfile  = cfg.settings.mqtt_keyfile,
            certfile = cfg.settings.mqtt_certfile,
            tls_version=ssl.PROTOCOL_SSLv23
        )

    if cfg.settings.mqtt_user:
        mqtt_client.username_pw_set(cfg.settings.mqtt_user, cfg.settings.mqtt_password)
    try:
        print_line('Connecting to MQTT broker -->')
        mqtt_client.connect(cfg.settings.mqtt_server,
                            cfg.settings.mqtt_port,
                            cfg.settings.mqtt_keepalive)
    except:
        print_line('MQTT connection error. Please check your settings in the ' +\
                'configuration file "config.ini"', error=True, sd_notify=True)

    return mqtt_client


#############################################################################################
# MQTT - Message call back functions and subscriptions (Paho / uMQTT)
#############################################################################################
def mqtt_setup_messages():
    """
    Subscribe to MQTT topics and set up message callbacks
    
    Parameters:
        mqtt_client (Client): MQTT Client
        settings (Settings):  Settings instance
        sensors (Sensor{}):   dictionary of Sensor class
    """
    if sys.implementation.name != "micropython":
        # Set topic specific message handlers
        mqtt_client.message_callback_add(cfg.settings.base_topic_flora + '/man_report_cmd', mqtt_man_report_cmd)
        mqtt_client.message_callback_add(cfg.settings.base_topic_flora + '/man_irr_cmd', mqtt_man_irr_cmd)
        mqtt_client.message_callback_add(cfg.settings.base_topic_flora + '/man_irr_duration_ctrl', mqtt_man_irr_duration_ctrl)
        mqtt_client.message_callback_add(cfg.settings.base_topic_flora + '/auto_report_ctrl', mqtt_auto_report_ctrl)
        mqtt_client.message_callback_add(cfg.settings.base_topic_flora + '/auto_irr_ctrl', mqtt_auto_irr_ctrl)

        # Message handler for reception of all other subsribed topics
        mqtt_client.on_message = mqtt_on_message
    else:
        # umqtt only supports a single callback for all topics! 
        mqtt_client.set_callback(mqtt_umqtt_cb)


    # Subscribe to flora control MQTT topics
    for topic in ['man_report_cmd', 'man_irr_cmd', 'man_irr_duration_ctrl', 'auto_report_ctrl', 'auto_irr_ctrl', 'sleep_dis_ctrl']:
        print_line('Subscribing to MQTT topic ' + cfg.settings.base_topic_flora + '/' + topic,
                   console=True, sd_notify=True)
        mqtt_client.subscribe(cfg.settings.base_topic_flora + '/' + topic, lim_qos(2))

    if (cfg.settings.sensor_interface == 'mqtt'):
        # Subscribe all MQTT sensor topics, e.g. "miflora-mqtt-daemon/appletree/moisture"
        for sensor in s.sensors:
            print_line('Subscribing to MQTT topic ' + cfg.settings.base_topic_sensors + '/' + sensor,
                    console=True, sd_notify=True)
            mqtt_client.subscribe(cfg.settings.base_topic_sensors + '/' + sensor)


#############################################################################################
# MQTT - Eclipse Paho callbacks - http://www.eclipse.org/paho/clients/python/docs/#callbacks
#############################################################################################
def mqtt_on_connect(client, userdata, flags, rc):
    """
    MQTT client connect initialization callback function

    Parameters:
        client: client instance for this callback
        userdata: private user data as set in Client() or user_data_set()
        flags: response flags sent by the broker
        rc: return code - connection result
    """
    if rc == 0:
        print_line('<-- MQTT connection established', console=True, sd_notify=True)
    else:
        print_line('Connection error with result code {} - {}'.format(str(rc),
                   mqtt.connack_string(rc)), error=True)
        #kill main thread
        os._exit(1)

    # Set up MQTT message subscription and handlers
    #mqtt_setup_messages(mqtt_client, cfg.settings, s.sensors)
    mqtt_setup_messages()


def mqtt_man_report_cmd(client, userdata, msg):
    """
    Send report as mail.
    
    This is an MQTT message callback function
    
    Parameters:
        client: client instance for this callback
        userdata: private user data as set in Client() or user_data_set()
        msg: an instance of MQTTMessage. This is a class with members topic, payload, qos, retain
    """
    #(tank, pump) = userdata
    
    print_line('MQTT message "man_report_cmd" received.', console=True, sd_notify=True)
    
    # To avoid Out-of-Memory exception in SMTP constructor (using SSL) on ESP32,
    # disconnect MQTT client before sending mail
    if sys.implementation.name == "micropython":
        client.disconnect()

    r.Report(cfg.settings, s.sensors, tank.tank, pump.pump)
    
    # Reconnect MQTT client
    if sys.implementation.name == "micropython":
        mqtt_umqtt_reconnect()

    
def mqtt_man_irr_cmd(client, userdata, msg):
    """
    Run irrigation for <irr_duration> seconds.

    This is an MQTT message callback function

    Parameters:
        client: client instance for this callback
        userdata: private user data as set in Client() or user_data_set()
        msg: an instance of MQTTMessage. This is a class with members topic, payload, qos, retain
    """
    #(tank, pump) = userdata
    
    print_line('MQTT message "man_irr_cmd" received', console=True, sd_notify=True)
    if (pump.pump.busy):
        print_line('Pump already busy ({:s}), ignoring request'
                   .format("manual" if (pump.pump.busy == PUMP_BUSY_MAN) else "auto"),
                   console=True, sd_notify=True)
        return

    client.publish(cfg.settings.base_topic_flora + '/man_irr_stat', str(1), lim_qos(2))
    pump.pump.busy = PUMP_BUSY_MAN


def mqtt_man_irr_duration_ctrl(client, userdata, msg):
    """
    Set manual irrigation duration (<irr_duration_man>)

    This is an MQTT message callback function

    In this case, MQTT Dash sends the value as string/byte array.
    (b'65' means integer value 65)
    The response message contains the original payload, which
    is used by MQTT Dash to set the visual state.

    Parameters:
        client: client instance for this callback
        userdata: private user data as set in Client() or user_data_set()
        msg: an instance of MQTTMessage. This is a class with members topic, payload, qos, retain
    """
    cfg.settings.irr_duration_man = int(msg.payload)

    print_line('MQTT message "man_irr_duration_ctrl({})" received'.format(cfg.settings.irr_duration_man),
               console=True, sd_notify=True)
    client.publish(cfg.settings.base_topic_flora + '/man_irr_duration_stat', msg.payload)


def mqtt_auto_report_ctrl(client, userdata, msg):
    """
    Switch auto reporting on/off)

    This is an MQTT message callback function

    In this case, MQTT Dash sends the value as string/byte array.
    (b'0'/b'1' means integer value 0/1)
    The response message contains the original payload, which
    is used by MQTT Dash to set the visual state.

    Parameters:
        client: client instance for this callback
        userdata: private user data as set in Client() or user_data_set()
        msg: an instance of MQTTMessage. This is a class with members topic, payload, qos, retain
    """
    cfg.settings.auto_report = int(msg.payload)

    print_line('MQTT message "auto_report_ctrl({})" received'.format(cfg.settings.auto_report),
               console=True, sd_notify=True)
    client.publish(cfg.settings.base_topic_flora + '/auto_report_stat', msg.payload)


def mqtt_auto_irr_ctrl(client, userdata, msg):
    """
    Switch auto irrigation on/off

    This is an MQTT message callback function

    In this case, MQTT Dash sends the value as string/byte array.
    (b'0'/b'1' means integer value 0/1)
    The response message contains the original payload, which
    is used by MQTT Dash to set the visual state.
    
    Parameters:
        client: client instance for this callback
        userdata: private user data as set in Client() or user_data_set()
        msg: an instance of MQTTMessage. This is a class with members topic, payload, qos, retain    
    """
    cfg.settings.auto_irrigation = int(msg.payload)

    print_line('MQTT message "auto_irr_ctrl({})" received'.format(cfg.settings.auto_irrigation),
               console=True, sd_notify=True)
    client.publish(cfg.settings.base_topic_flora + '/auto_irr_stat', msg.payload)

def mqtt_sleep_dis_ctrl(client, userdata, msg):
    """
    Disable deep sleep mode

    This is an MQTT message callback function

    In this case, MQTT Dash sends the value as string/byte array.
    (b'0'/b'1' means integer value 0/1)
    The response message contains the original payload, which
    is used by MQTT Dash to set the visual state.
    
    Parameters:
        client: client instance for this callback
        userdata: private user data as set in Client() or user_data_set()
        msg: an instance of MQTTMessage. This is a class with members topic, payload, qos, retain    
    """
    sleep_disable = int(msg.payload)
    cfg.settings.deep_sleep = not(sleep_disable)

    print_line('MQTT message "sleep_dis_ctrl({})" received'.format(sleep_disable),
               console=True, sd_notify=True)
    client.publish(cfg.settings.base_topic_flora + '/sleep_dis_stat', str(1 if sleep_disable else 0))


def mqtt_on_message(client, userdata, msg):
    """
    Handle all other MQTT messages, i.e. those with sensor data.

    This is an MQTT message callback function.

    Parameters:
        client: client instance for this callback
        userdata: private user data as set in Client() or user_data_set()
        msg: an instance of MQTTMessage. This is a class with members topic, payload, qos, retain    
    """
    base_topic, sensor = msg.topic.split('/')

    # Convert JSON ecoded data to dictionary
    message = json.loads(msg.payload.decode('utf-8'))

    if (VERBOSITY > 0):
        print_line('MQTT message from {}: {}'.format(sensor, message))

    # Discard data if moisture value suddenly drops to zero
    # FIXME: Is this still useful?
    if ((float(message['moisture']) == 0) and
        (s.sensors[sensor].moist > 5)):
        return

    s.sensors[sensor].update_sensor(
        float(message['temperature']),
        int(message['conductivity']),
        int(message['moisture']),
        int(message['light']),
        int(message['battery'])
    )
