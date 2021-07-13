###############################################################################
# secrets.py
#
# This module provides user defined constants to be kept secret.
#
# Some settings can be overridden by config.ini
#
# created: 02/2021 updated: 03/2021
#
# This program is Copyright (C) 02/2021 Matthias Prinke
# <m.prinke@arcor.de> and covered by GNU's GPL.
# In particular, this program is free software and comes WITHOUT
# ANY WARRANTY.
#
# History:
#
# 20210212 Initial version
# 20210316 Added list of WLAN access points (NETWORKS)
#
# ToDo:
# - 
#
###############################################################################

# List of known Access Points
# Example:
#NETWORKS = [ # SSID, PWD, [MAC] (Optional)
#	['ssid1', 'pwd1', ['25288b12423d4']],
#	['ssid2', 'pwd2'],
#	['ssidN', 'pwdN']
#]

NETWORKS = [ # SSID, PWD, [MAC] (Optional)
	['ssid1', 'pwd1', ['25288b12423d4']],
	['ssid2', 'pwd2'],
	['ssidN', 'pwdN']
]


MQTT_USERNAME = 'mqtt_username'
MQTT_PASSWORD = 'mqtt_password'

SMTP_LOGIN    = 'smtp_login'
SMTP_PASSWD   = 'smtp_passwd'
SMTP_EMAIL    = 'smtp_sender@somedomain.org'
SMTP_RECEIVER = 'smtp_receiver@someotherdomain.com'
