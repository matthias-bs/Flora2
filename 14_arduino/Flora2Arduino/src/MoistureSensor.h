///////////////////////////////////////////////////////////////////////////////
// src/MoistureSensor.h
//
// Reads capacitive soil moisture sensors via ADC (analogReadMilliVolts).
//
// Calibration: dry sensor outputs ~1250 mV, saturated ~900 mV.
// These defaults can be overridden via setCalibration() or Flora2Cfg.h.
//
// MIT License — Copyright (c) 2026 Matthias Prinke
///////////////////////////////////////////////////////////////////////////////

#pragma once
#include <Arduino.h>

class MoistureSensor {
public:
    MoistureSensor();

    /// Override calibration points (mV at 0% and 100% moisture).
    void setCalibration(uint16_t dry_mV, uint16_t wet_mV);

    /// Read a single sensor and return moisture percentage (0–100 %).
    /// Returns -1.0f if the pin is invalid or reading fails.
    float getMoisture(int pin);

private:
    uint16_t _dry_mV;  ///< ADC mV corresponding to 0% moisture (completely dry)
    uint16_t _wet_mV;  ///< ADC mV corresponding to 100% moisture (saturated)
};
