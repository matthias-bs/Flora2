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
# 20250402 Code improvements
# 20250403 Added singleton pattern
#
# Backlog:
# -
#
###############################################################################
"""WiFi connection module."""

from time import sleep
from secrets import NETWORKS
from network import WLAN, STA_IF, AP_IF


USE_AP = False  # Turn On Internal AP After Failed WiFi Station Connection


class WiFiManager:
    """Singleton class to manage WiFi connections."""
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

        self.station = WLAN(STA_IF)
        self.station.active(True)
        self.ap = WLAN(AP_IF)
        self.ap.active(False)

    def connect(self, timeout=10):
        """Connect to a WiFi network."""
        print("Scanning for available networks...")
        available_networks = {n[0].decode(): n for n in self.station.scan()}

        for ssid, credentials in NETWORKS:
            if ssid in available_networks:
                print(f"Connecting to {ssid}...")
                self.station.connect(ssid, credentials)
                for _ in range(timeout * 10):  # Wait for connection
                    if self.station.isconnected():
                        print(f"Connected to {ssid}")
                        print(f"IP Address: {self.station.ifconfig()[0]}")
                        return True
                    sleep(0.1)
                print(f"Failed to connect to {ssid}")
        print("No known networks available.")
        if USE_AP:
            self.start_ap()
        return False

    def start_ap(self):
        """Start the device as an access point."""
        print("Starting access point...")
        self.ap.active(True)
        self.ap.config(essid="MyAP", password="password123")
        print(f"Access point started with IP: {self.ap.ifconfig()[0]}")

    def disconnect(self):
        """Disconnect from the current WiFi network."""
        if self.station.isconnected():
            print("Disconnecting from WiFi...")
            self.station.disconnect()
            print("Disconnected.")

    def is_connected(self):
        """Check if the device is connected to WiFi."""
        return self.station.isconnected()


    def deinit(self):
        """Deactivate the WiFi station."""
        if self.station.active():
            self.station.active(False)

# Create a singleton instance
wifi_manager = WiFiManager()
