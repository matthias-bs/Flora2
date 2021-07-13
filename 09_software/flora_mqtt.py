###############################################################################
# flora_mqtt.py
#
# This module provides the flora MQTT functions
#
# The module contains code for two different MQTT client implementations -
# - Eclipse Paho MQTT client
#   https://www.eclipse.org/paho/index.php?page=clients/python/index.php
# - uMQTT MicroPython MQTT client
#   https://github.com/micropython/micropython-lib/tree/master/umqtt.robust
#
# created: 03/2021 updated: 06/2021
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
# 20210605 Added handling of 2nd pump
# 20210627 Added workarounds for MQTT over TLS
#          removed non-MicroPython MQTT code
#          added exception handling in mqtt_man_irr_duration_ctrl()
#
# ToDo:
# - 
#
###############################################################################

import sys
import os
import json
import pump as m_pump

if sys.implementation.name == "micropython":
    import ussl
    from umqtt.robust2 import MQTTClient
    import machine
    import ubinascii
else:
    import ssl
    import paho.mqtt.client as mqtt

import config as cfg
import sensor as s
import report as m_report
from time import sleep, sleep_ms
from config import DEBUG, VERBOSITY, PUMP_BUSY_MAN
from print_line import *


##############################################################################
# Global variables
##############################################################################
mqtt_client = None


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


def mqtt_umqtt_init():
    """
    Init MQTT client and connect to MQTT broker

    Parameters:
        settings (Settings): Settings instance
        
    Returns:
        MQTT client instance
    """
    global mqtt_client
    
    unique_id = ubinascii.hexlify(machine.unique_id()).decode("ascii")
    
    if cfg.settings.mqtt_tls:
        with open(cfg.settings.mqtt_ca_cert, "r") as f:
            cert = f.read()
    else:
        cert = None

    try:
        mqtt_client = MQTTClient(client_id=(cfg.settings.base_topic_flora + unique_id),
                        server=cfg.settings.mqtt_server,
                        port=cfg.settings.mqtt_port,
                        user=cfg.settings.mqtt_user,
                        password=cfg.settings.mqtt_password,
                        keepalive=cfg.settings.mqtt_keepalive,
                        socket_timeout=40 if cfg.settings.mqtt_tls else 6,
                        ssl=cfg.settings.mqtt_tls,
                        ssl_params={"cert":cert,"server_side":False}
        )
        mqtt_client.set_last_will(cfg.settings.base_topic_flora + '/status', "dead", qos=1, retain=True)
        
        # BEGIN FIXME
        print_line('Connecting to MQTT broker -->')
        rc = mqtt_client.connect(clean_session=False)
    except Exception as e:
        print_line('<-- Cannot connect to  MQTT broker: ' + str(e))
        raise
        
    print_line('<-- MQTT connection established ({} session)'.format("existing" if rc else "clean"), sd_notify=True)
    
    # FIXME Something is quite different/wrong with SSL sockets. To allow non-secure and secure
    # communication, we currently do not check the connection now, because that would fail in the latter case.
#    else:
#        while mqtt_client.is_conn_issue():
#            # If the connection is successful, the is_conn_issue
#            # method will not return a connection error.
#            mqtt_client.reconnect()
#            sleep_ms(500)
#        mqtt_client.resubscribe()
    
    # Set up MQTT message subscription and handlers
    mqtt_setup_messages(not(rc))
    # END FIXME


def mqtt_umqtt_cb(topic, msg, retained, dup):
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
        print_line("uMQTT message handler: topic '{}' / msg '{}' / retained: {} / dup: {}.".format(topic, msg, retained, dup),
                   sd_notify=True)
    
    message = MQTTMessage(topic, msg)
    
    if (topic == cfg.settings.base_topic_flora + '/man_report_cmd'):
        mqtt_man_report_cmd(mqtt_client, None, message)
    elif (topic == cfg.settings.base_topic_flora + '/man_irr_cmd'):
        mqtt_man_irr_cmd(mqtt_client, None, message)
    elif (topic == cfg.settings.base_topic_flora + '/man_irr_duration_ctrl'):
        mqtt_man_irr_duration_ctrl(mqtt_client, None, message)
    elif (topic == cfg.settings.base_topic_flora + '/auto_report_ctrl'):
        mqtt_auto_report_ctrl(mqtt_client, None, message)
    elif (topic == cfg.settings.base_topic_flora + '/auto_irr_ctrl'):
        mqtt_auto_irr_ctrl(mqtt_client, None, message)
    elif (topic == cfg.settings.base_topic_flora + '/sleep_dis_ctrl'):
        mqtt_sleep_dis_ctrl(mqtt_client, None, message)
    else:
        mqtt_on_message(mqtt_client, None, message)


#############################################################################################
# MQTT - Message call back functions and subscriptions (Paho / uMQTT)
#
# Eclipse Paho callbacks: http://www.eclipse.org/paho/clients/python/docs/#callbacks
#############################################################################################
def mqtt_setup_messages(subscribe = True):
    """
    Subscribe to MQTT topics and set up message callbacks
    
    Subscription can be ommitted if connecting to persisting session.
    
    Parameters:
        subsribe (bool): if true, subscribe to messages
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

    if (subscribe):
        # Subscribe to flora control MQTT topics
        for topic in ['man_report_cmd', 'man_irr_cmd', 'man_irr_duration_ctrl', 'auto_report_ctrl', 'auto_irr_ctrl', 'sleep_dis_ctrl']:
            print_line('Subscribing to MQTT topic ' + cfg.settings.base_topic_flora + '/' + topic,
                    sd_notify=True)
            mqtt_client.subscribe(cfg.settings.base_topic_flora + '/' + topic, qos=1)

        if (cfg.settings.sensor_interface == 'mqtt'):
            # Subscribe all MQTT sensor topics, e.g. "miflora-mqtt-daemon/appletree/moisture"
            for sensor in s.sensors:
                print_line('Subscribing to MQTT topic ' + cfg.settings.base_topic_sensors + '/' + sensor,
                        sd_notify=True)
                mqtt_client.subscribe(cfg.settings.base_topic_sensors + '/' + sensor)


#############################################################################################
# MQTT callbacks
#############################################################################################
def mqtt_man_report_cmd(client, userdata, msg):
    """
    Send report as mail.
    
    This is an MQTT message callback function
    
    Parameters:
        client: client instance for this callback
        userdata: private user data as set in Client() or user_data_set()
        msg: an instance of MQTTMessage. This is a class with members topic, payload, qos, retain
    """
    print_line('MQTT message "man_report_cmd" received.', sd_notify=True)
    
    # Defer sending until sensor data has been read
    cfg.settings.man_report = True

    
def mqtt_man_irr_cmd(client, userdata, msg):
    """
    Run irrigation for <irr_duration> seconds.

    This is an MQTT message callback function

    Parameters:
        client: client instance for this callback
        userdata: private user data as set in Client() or user_data_set()
        msg: an instance of MQTTMessage. This is a class with members topic, payload, qos, retain
    """
    val = int(msg.payload)
    print_line('MQTT message "man_irr_cmd({})" received'.format(val), sd_notify=True)
    if ((val == 1) or (val == 2)):
        idx = val - 1
        if (m_pump.pumps[idx].busy):
            print_line('Pump #{} already busy ({:s}), ignoring request'
                       .format(val, "manual" if (m_pump.pumps[idx].busy == PUMP_BUSY_MAN) else "auto"),
                    sd_notify=True)
            return

        client.publish(cfg.settings.base_topic_flora + '/man_irr_stat', str(val), qos = 1)
        m_pump.pumps[idx].busy = PUMP_BUSY_MAN


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
    try:
        cfg.settings.irr_duration_man = int(msg.payload)
    except ValueError:
        print_line('MQTT message "man_irr_duration_ctrl({})" received - syntax error'.format(msg.payload),
                warning=True, sd_notify=True)
    else:
        print_line('MQTT message "man_irr_duration_ctrl({})" received'.format(cfg.settings.irr_duration_man),
                sd_notify=True)
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
               sd_notify=True)
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
               sd_notify=True)
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
               sd_notify=True)
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
        print_line('MQTT message from {}: {}'.format(sensor, message),
                   sd_notify=True)

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
