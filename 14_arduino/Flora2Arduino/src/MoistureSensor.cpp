///////////////////////////////////////////////////////////////////////////////
// src/MoistureSensor.cpp
//
// MIT License — Copyright (c) 2026 Matthias Prinke
///////////////////////////////////////////////////////////////////////////////

#include "MoistureSensor.h"
#include "../Flora2Cfg.h"

MoistureSensor::MoistureSensor()
    : _dry_mV(MOISTURE_DRY_MV), _wet_mV(MOISTURE_WET_MV)
{}

void MoistureSensor::setCalibration(uint16_t dry_mV, uint16_t wet_mV)
{
    _dry_mV = dry_mV;
    _wet_mV = wet_mV;
}

float MoistureSensor::getMoisture(int pin)
{
    if (pin < 0) return -1.0f;

    // Average multiple samples to reduce ADC noise
    uint32_t sum = 0;
    for (int i = 0; i < MOISTURE_SAMPLES; i++) {
        sum += analogReadMilliVolts(pin);
        delay(5);
    }
    uint16_t raw_mV = (uint16_t)(sum / MOISTURE_SAMPLES);

    // Linear transfer: higher mV = drier soil → invert
    if (raw_mV >= _dry_mV) return 0.0f;
    if (raw_mV <= _wet_mV)  return 100.0f;

    float pct = 100.0f * ((float)(_dry_mV - raw_mV)) /
                          ((float)(_dry_mV - _wet_mV));
    return pct;
}
