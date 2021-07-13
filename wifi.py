###############################################################################
# wifi.py
#
# This module provides WiFi connection functions
#
#
# created: 03/2021 updated: 03/2021
#
# This program is Copyright (C) 03/2021 Matthias Prinke
# <m.prinke@arcor.de> and covered by GNU's GPL.
# In particular, this program is free software and comes WITHOUT
# ANY WARRANTY.
#
# History:
#
# 20210330 Extracted from boot.py
#
# ToDo:
# - 
#
###############################################################################

from time import sleep
from network import WLAN, STA_IF, AP_IF, STAT_IDLE, STAT_CONNECTING, STAT_WRONG_PASSWORD, STAT_NO_AP_FOUND, STAT_GOT_IP
from ubinascii import hexlify

from secrets import *


USE_AP = False # Turn On Internal AP After Failed WiFi Station Connection
station = None
local_ap = None

# connectWiFi - allows to connect to one access point from a list
# https://forum.micropython.org/viewtopic.php?t=2951

def init():
    global station
    global local_ap
    
    station = WLAN(STA_IF)
    local_ap = WLAN(AP_IF)

def connectWiFi(station):
    if not station.active():
        station.active(True)
    
    if waitForConnection(station):
        return True

    aps = station.scan()
    aps.sort(key=lambda ap:ap[3], reverse=True)

    for ap in aps:
        for net in NETWORKS:
            found = False
            if ap[0].decode('UTF-8') == net[0]:
                found = True
            elif len(net) == 3:
                for mac in net[2]:
                    if hexlify(ap[1]).decode('UTF-8') == mac:
                        found = True
                        break

            if found:
                station.connect(net[0], net[1])
                if waitForConnection(station):
                    if USE_AP and local_ap.active():
                        local_ap.active(False)
                    return True

    if USE_AP and not local_ap.active():
        local_ap.active(True)

    return False

def deinit():
    global station
    global local_ap
    
    if station.active():
        station.active(False)
    
    station = None
    local_ap = None

def waitForConnection(station):
    while station.status() == STAT_CONNECTING:
        sleep(0.25)

    return station.isconnected()

