###############################################################################
# garbage_collect.py
#
# This module provides wrapper functions for
# garbage collection and memory information
# on MicroPython
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
# 20210318 Created
#
# ToDo:
# - 
#
###############################################################################

import sys

if sys.implementation.name == "micropython":
    import gc
    import micropython

def gcollect():
    if sys.implementation.name == "micropython":
        gc.collect()

def meminfo(text):
    if sys.implementation.name == "micropython":
        print('[{}]'.format(text))
        micropython.mem_info()
