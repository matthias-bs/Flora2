###############################################################################
# secrets.py
#
# This module provides user defined constants to be kept secret.
#
# Some settings can be overridden by config.ini
#
# created: 02/2021 updated: 02/2021
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

]



MQTT_USERNAME = ''
MQTT_PASSWORD = ''

SMTP_LOGIN    = ''
SMTP_PASSWD   = ''
SMTP_EMAIL    = ''
SMTP_RECEIVER = ''
