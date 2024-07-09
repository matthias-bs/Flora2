###############################################################################
# Alert.py
#
# This module provides a stub as (non-functional!) replacement for RPi.GPIO
# on other systems than Raspberry Pi.
#
# - tries to import RPi.GPIO as GPIO
# - if this fails, provides instance GPIO of class Gpio
#
# created: 01/2021 updated: 01/2021
#
# This program is Copyright (C) 01/2021 Matthias Prinke
# <m.prinke@arcor.de> and covered by GNU's GPL.
# In particular, this program is free software and comes WITHOUT
# ANY WARRANTY.
#
# History:
#
# 20210117 Extracted from flora.py
#
# ToDo:
# - 
#
###############################################################################

try:
    import RPi.GPIO as GPIO
    USE_GPIO_STUB = False
except:
    USE_GPIO_STUB = True
    print("Using GPIO stub")
else:
    print("Using RPi.GPIO")

#########################################################################################
# Gpio class - A stub as replacement for RPi.GPIO on other systems than Raspberry Pi
#########################################################################################
if (USE_GPIO_STUB):
    class Gpio:
        def __init__(self):
            self.BCM = 0
            self.IN = 0
            self.OUT = 1
            self.LOW = 0
            self.HIGH = 1

        def setmode(self, mode):
            pass

        def setup(self, pin, direction):
            pass

        def input(self, pin):
            return (False)

        def output(self, pin, val):
            pass
           
# Use stub for RPi.GPIO on other systems than Raspberry Pi
if (USE_GPIO_STUB):
    GPIO = Gpio()
