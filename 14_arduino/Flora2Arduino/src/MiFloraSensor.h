///////////////////////////////////////////////////////////////////////////////
// src/MiFloraSensor.h
//
// BLE direct-GATT reader for Xiaomi HHCCJCY01HHCC (MiFlora) plant sensors.
//
// Design:
//   • Uses NimBLE-Arduino central mode to connect to configured sensor MACs.
//   • Reads sensor data via control/data characteristics (1a00/1a01).
//   • Reads battery via characteristic 1a02 and caches values in NVS Preferences.
//
// MIT License — Copyright (c) 2026 Matthias Prinke
///////////////////////////////////////////////////////////////////////////////

#pragma once
#include <Arduino.h>
#include <vector>
#include <string>
#include "../Flora2Cfg.h"
#include "ConfigLoader.h"

class MiFloraSensor {
public:
    MiFloraSensor();

    /// GATT connect to each sensor and read sensor values + battery level.
    /// Caches battery results in NVS Preferences ("mf_batt").
    /// @param addresses   BLE MAC addresses to connect to
    /// @param data        Sensor data array — battery field updated in-place
    /// @param numSensors  Number of sensors
    void readBattery(const std::vector<std::string>& addresses,
                     PlantSensorData*               data,
                     uint8_t                        numSensors);
};
