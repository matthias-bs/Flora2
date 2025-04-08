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
# 20250306 Removed report command/control
#          Added MQTT discovery messages for Home Assistant
# 20250403 Code quality improvements
# 20250404 Changed to Singleton class
# 20250408 Code quality improvements
#
# Backlog:
# -
#
###############################################################################
"""MQTT client for Flora2"""

import sys
import json
import binascii
import machine
#from time import sleep_ms

# https://pypi.org/project/micropython-umqtt.robust2/
from umqtt.robust2 import MQTTClient

import pump
from config import config, VERBOSITY, PUMP_BUSY_MAN
import sensor
from print_line import print_line


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


class FloraMQTT:
    """
    Init MQTT client and connect to MQTT broker

    Parameters:
        settings (Settings): Settings instance

    Returns:
        MQTT client instance
    """
    _instance = None  # Class-level variable to hold the singleton instance
    _initialized = False  # Define _initialized at the class level

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._initialized:
            return  # Prevent re-initialization
        self._initialized = True

        unique_id = binascii.hexlify(machine.unique_id()).decode("ascii")

        if config.mqtt_tls:
            with open(config.mqtt_ca_cert, "r", encoding='utf-8') as f:
                cert = f.read()
        else:
            cert = None

        try:
            self.client = MQTTClient(client_id=(config.base_topic_flora + unique_id),
                                    server=config.mqtt_server,
                                    port=config.mqtt_port,
                                    user=config.mqtt_user,
                                    password=config.mqtt_password,
                                    keepalive=config.mqtt_keepalive,
                                    socket_timeout=40 if config.mqtt_tls else 6,
                                    ssl=config.mqtt_tls,
                                    ssl_params={"cert":cert,"server_side":False},
            )
            self.client.set_last_will(config.base_topic_flora + '/status', "dead",
                                      qos=1, retain=True)

            # BEGIN FIXME
            print_line('Connecting to MQTT broker -->')
            rc = self.client.connect(clean_session=False)
        except Exception as e:
            print_line('<-- Cannot connect to  MQTT broker: ' + str(e))
            raise

        print_line(f'<-- MQTT connection established ({"existing" if rc else "clean"} session)',
                   sd_notify=True)

        # FIXME       # pylint: disable=fixme
        # Something is quite different/wrong with SSL sockets. To allow non-secure and secure
        # communication, we currently do not check the connection now, because that would fail
        # in the latter case.
        #    else:
        #        while mqtt_client.is_conn_issue():
        #            # If the connection is successful, the is_conn_issue
        #            # method will not return a connection error.
        #            mqtt_client.reconnect()
        #            sleep_ms(500)
        #        mqtt_client.resubscribe()

        # Set up MQTT message subscription and handlers
        self.mqtt_setup_messages(not rc)
        # END FIXME


    def mqtt_umqtt_cb(self, topic, msg, retained, dup):
        """
        uMQTT sub message callback

        Uses global vars <config> and <mqtt_client>!!!

        Parameters:
            topic (bytes):  MQTT message topic
            msg (bytes):    MQTT message payload
        """
        # Convert topic from bytes to string
        topic = topic.decode('utf-8')

        if VERBOSITY > 1:
            print_line(f"uMQTT message handler: topic '{topic}' / msg '{msg}'" +
                       f"/ retained: {retained} / dup: {dup}.",
                    sd_notify=True)

        message = MQTTMessage(topic, msg)

        if topic == config.base_topic_flora + '/man_irr_cmd':
            self.mqtt_man_irr_cmd(self.client, None, message)
        elif topic == config.base_topic_flora + '/man_irr_duration_ctrl':
            self.mqtt_man_irr_duration_ctrl(self.client, None, message)
        elif topic == config.base_topic_flora + '/auto_irr_ctrl':
            self.mqtt_auto_irr_ctrl(self.client, None, message)
        elif topic == config.base_topic_flora + '/sleep_dis_ctrl':
            self.mqtt_sleep_dis_ctrl(self.client, None, message)
        else:
            self.mqtt_on_message(self.client, None, message)


    def publish_discovery_sensor(self, name):
        """
        Publish MQTT discovery messages for Home Assistant

        Parameters:
            name (string): sensor name (same as data topic)
        """
        state_topic = f"{config.base_topic_flora}/{name}"
        sensor_name = f"{config.base_topic_flora}_{name}"

        if name == "temperature":
            sensors = [
                {"name": f"{sensor_name}", "stat_t": f"{state_topic}", "dev_cla": "temperature",
                 "val_tpl": "{{ value }}", "unit_of_meas": "°C"},
            ]
        elif name == "ubatt":
            sensors = [
                {"name": f"{sensor_name}", "stat_t": f"{state_topic}", "dev_cla": "voltage",
                 "val_tpl": "{{ value }}", "unit_of_meas": "mV"},
            ]
        elif name == "tank":
            sensors = [
                {
                    "name": f"{sensor_name}_int", "stat_t": f"{config.base_topic_flora}/tank",
                    "dev_cla": "enum", "val_tpl": "{{ value }}", "unit_of_meas": ""
                },
                {
                    "name": f"{sensor_name}_str", "stat_t": f"{config.base_topic_flora}/system",
                    "dev_cla": "enum", "val_tpl": "{{ value_json.tank }}", "unit_of_meas": ""
                }
            ]
        elif name == "weather":
            sensors = [
                {
                    "name": f"{name}_humidity", "stat_t": f"{state_topic}", "dev_cla": "humidity",
                    "val_tpl": "{{ value_json.humidity | float }}", "unit_of_meas": "%"
                },
                {
                    "name": f"{name}_temperature", "stat_t": f"{state_topic}",
                    "dev_cla": "temperature", "val_tpl": "{{ value_json.temperature | float }}",
                    "unit_of_meas": "°C"
                },
                {
                    "name": f"{name}_pressure", "stat_t": f"{state_topic}",
                    "dev_cla": "atmospheric_pressure",
                    "val_tpl": "{{ value_json.pressure | float }}",
                    "unit_of_meas": "hPa"},
            ]
        else:
            sensors = [
                {
                    "name": f"{name}_battery", "stat_t": f"{state_topic}", "dev_cla": "battery",
                    "val_tpl": "{{ value_json.battery | int }}", "unit_of_meas": "%"
                },
                {
                    "name": f"{name}_brightness", "stat_t": f"{state_topic}",
                    "dev_cla": "illuminance", "val_tpl": "{{ value_json.light | int }}",
                    "unit_of_meas": "lx"
                },
                {
                    "name": f"{name}_moisture", "stat_t": f"{state_topic}",
                    "dev_cla": "moisture", "val_tpl": "{{ value_json.moisture | int }}",
                    "unit_of_meas": "%"
                },
                {
                    "name": f"{name}_temperature", "stat_t": f"{state_topic}",
                    "dev_cla": "temperature", "val_tpl": "{{ value_json.temperature | float }}",
                    "unit_of_meas": "°C"
                },
                {
                    "name": f"{name}_conductivity", "stat_t": f"{state_topic}",
                    "dev_cla": "conductivity", "val_tpl": "{{ value_json.conductivity | int }}",
                    "unit_of_meas": "µS/cm"
                }
            ]

        for s in sensors:
            discovery_topic = f"homeassistant/sensor/{s['name']}/config"
            discovery_payload = {
                "name": s["name"],
                "stat_t": s["stat_t"],
                "val_tpl": s["val_tpl"],
                "unit_of_meas": s["unit_of_meas"],
                "dev_cla": s["dev_cla"],
                "uniq_id": s["name"],
                "dev": {
                    "identifiers": ["plant_sensor"],
                    "name": "Flora2",
                }
            }
            self.client.publish(discovery_topic, json.dumps(discovery_payload).encode("utf-8"))
            self.client.send_queue()


    #############################################################################################
    # MQTT - Message call back functions and subscriptions (Paho / uMQTT)
    #
    # Eclipse Paho callbacks: http://www.eclipse.org/paho/clients/python/docs/#callbacks
    #############################################################################################
    def mqtt_setup_messages(self, subscribe = True):
        """
        Subscribe to MQTT topics and set up message callbacks

        Subscription can be ommitted if connecting to persisting session.

        Parameters:
            subsribe (bool): if true, subscribe to messages
        """
        if sys.implementation.name != "micropython":
            # Set topic specific message handlers
            self.client.message_callback_add(config.base_topic_flora + '/man_irr_cmd',
                                             self.mqtt_man_irr_cmd)
            self.client.message_callback_add(config.base_topic_flora + '/man_irr_duration_ctrl',
                                             self.mqtt_man_irr_duration_ctrl)
            self.client.message_callback_add(config.base_topic_flora + '/auto_irr_ctrl',
                                             self.mqtt_auto_irr_ctrl)

            # Message handler for reception of all other subsribed topics
            self.client.on_message = self.mqtt_on_message
        else:
            # umqtt only supports a single callback for all topics!
            self.client.set_callback(self.mqtt_umqtt_cb)

        if subscribe:
            # Subscribe to flora control MQTT topics
            for topic in ['man_irr_cmd', 'man_irr_duration_ctrl', 'auto_irr_ctrl',
                          'sleep_dis_ctrl']:
                print_line(f'Subscribing to MQTT topic {config.base_topic_flora}/{topic}',
                        sd_notify=True)
                self.client.subscribe(config.base_topic_flora + '/' + topic, qos=1)

            if config.sensor_interface == 'mqtt':
                # Subscribe all MQTT sensor topics, e.g. "miflora-mqtt-daemon/appletree/moisture"
                for s in sensor.sensors:
                    print_line(f'Subscribing to MQTT topic {config.base_topic_sensors}/{s}',
                            sd_notify=True)
                    self.client.subscribe(config.base_topic_sensors + '/' + s)


    #############################################################################################
    # MQTT callbacks
    #############################################################################################
    def mqtt_man_irr_cmd(self, client, _userdata, msg):
        """
        Run irrigation for <irr_duration> seconds.

        This is an MQTT message callback function

        Parameters:
            client: client instance for this callback
            userdata: private user data as set in Client() or user_data_set()
            msg: instance of MQTTMessage. This is a class with members
                 topic, payload, qos, retain
        """
        val = int(msg.payload)
        print_line(f'MQTT message "man_irr_cmd({val})" received', sd_notify=True)
        if val in (1, 2):
            idx = val - 1
            if pump.pumps[idx].busy:
                mode = "manual" if (pump.pumps[idx].busy == PUMP_BUSY_MAN) else "auto"
                print_line(f'Pump #{val} already busy ({mode}), ignoring request',
                        sd_notify=True)
                return

            client.publish(config.base_topic_flora + '/man_irr_stat', str(val), qos = 1)
            pump.pumps[idx].busy = PUMP_BUSY_MAN


    def mqtt_man_irr_duration_ctrl(self, client, _userdata, msg):
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
            msg: instance of MQTTMessage. This is a class with members
                 topic, payload, qos, retain
        """
        try:
            config.irr_duration_man = int(msg.payload)
        except ValueError:
            print_line(f'MQTT message "man_irr_duration_ctrl({msg.payload})" received' +
                       ' - syntax error',
                    warning=True, sd_notify=True)
        else:
            print_line(f'MQTT message "man_irr_duration_ctrl({config.irr_duration_man})" received',
                    sd_notify=True)
            client.publish(config.base_topic_flora + '/man_irr_duration_stat', msg.payload)


    def mqtt_auto_irr_ctrl(self, client, _userdata, msg):
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
            msg: instance of MQTTMessage. This is a class with members
                 topic, payload, qos, retain
        """
        config.auto_irrigation = int(msg.payload)

        print_line(f'MQTT message "auto_irr_ctrl({config.auto_irrigation})" received',
                sd_notify=True)
        client.publish(config.base_topic_flora + '/auto_irr_stat', msg.payload)


    def mqtt_sleep_dis_ctrl(self, client, _userdata, msg):
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
            msg: instance of MQTTMessage. This is a class with members
                 topic, payload, qos, retain
        """
        sleep_disable = int(msg.payload)
        config.deep_sleep = not sleep_disable

        print_line(f'MQTT message "sleep_dis_ctrl({sleep_disable})" received',
                sd_notify=True)
        client.publish(config.base_topic_flora + '/sleep_dis_stat', str(1 if sleep_disable else 0))


    def mqtt_on_message(self, _client, _userdata, msg):
        """
        Handle all other MQTT messages, i.e. those with sensor data.

        This is an MQTT message callback function.

        Parameters:
            client: client instance for this callback
            userdata: private user data as set in Client() or user_data_set()
            msg: instance of MQTTMessage. This is a class with members
                 topic, payload, qos, retain
        """
        _base_topic, sens = msg.topic.split('/')

        # Convert JSON ecoded data to dictionary
        message = json.loads(msg.payload.decode('utf-8'))

        if VERBOSITY > 0:
            print_line('MQTT message from {sensor}: {message}', sd_notify=True)

        # Discard data if moisture value suddenly drops to zero
        if (float(message['moisture']) == 0) and \
            (sensor.sensors[sens].moist > 5):
            return

        sensor.sensors[sens].update_sensor(
            float(message['temperature']),
            int(message['conductivity']),
            int(message['moisture']),
            int(message['light']),
            int(message['battery'])
        )

# Create a global singleton instance
flora_mqtt = FloraMQTT()
