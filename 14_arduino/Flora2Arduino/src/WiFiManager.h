///////////////////////////////////////////////////////////////////////////////
// src/WiFiManager.h
//
// WiFi connection manager with multi-network support and NTP synchronisation.
//
// MIT License — Copyright (c) 2026 Matthias Prinke
///////////////////////////////////////////////////////////////////////////////

#pragma once
#include <Arduino.h>
#include <WiFi.h>

class WiFiMgr {
public:
    /// Try each network in WIFI_NETWORKS[] until one connects.
    /// @return true on success
    bool connect();

    /// Synchronise system clock via SNTP and wait for a valid time.
    /// Must be called after connect().
    /// @param tzInfo  POSIX timezone string (e.g. "CET-1CEST,M3.5.0,M10.5.0/3")
    /// @param server1 Primary NTP server
    /// @param server2 Secondary NTP server (can be empty string)
    /// @param server3 Tertiary NTP server (can be empty string)
    /// @return true if time is synchronised
    bool ntpSync(const char* tzInfo,
                 const char* server1,
                 const char* server2 = "",
                 const char* server3 = "");

    void disconnect();
    bool isConnected() const;
};
