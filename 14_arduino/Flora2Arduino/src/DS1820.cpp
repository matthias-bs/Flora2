///////////////////////////////////////////////////////////////////////////////
// src/DS1820.cpp
//
// MIT License — Copyright (c) 2026 Matthias Prinke
///////////////////////////////////////////////////////////////////////////////

#include "DS1820.h"
#include <string.h>  // memcpy
#include <utils/Placeholder.h>

static const char* TAG = "DS1820";

DS1820::DS1820(uint8_t pin)
    : _pin(pin), _ow(nullptr), _count(0)
{}

bool DS1820::begin()
{
    // OneWireNg performs GPIO setup in its constructor, so it must be
    // constructed here (in setup()), never as a global variable.
    if (!_ow) {
        _ow = new OneWireNg_CurrentPlatform(static_cast<unsigned>(_pin), false);
    }

    // Enumerate all supported Dallas thermometer family codes.
    _count = 0;
    for (const auto& id : *_ow) {
        if (DSTherm::getFamilyName(id) == nullptr) continue;  // skip unknowns
        if (_count >= DS1820_MAX_DEVICES) {
            log_w("%s: more than %d devices — ignoring the rest", TAG, DS1820_MAX_DEVICES);
            break;
        }
        memcpy(_ids[_count++], id, sizeof(OneWireNg::Id));
        log_d("%s: [%d] family 0x%02X", TAG, _count - 1, id[0]);
    }

    log_i("%s: Found %d device(s)", TAG, _count);
    return (_count > 0);
}

void DS1820::requestAll()
{
    if (!_ow) return;
    DSTherm drv(*_ow);
    // convertTempAll with SCAN_BUS: issues the conversion command to all
    // sensors at once then polls the bus until all conversions complete
    // (or MAX_CONV_TIME = 750 ms elapses for 12-bit resolution).
    drv.convertTempAll(DSTherm::SCAN_BUS);
}

float DS1820::getTemperatureC(uint8_t index) const
{
    if (!_ow || index >= _count) return -127.0f;

    DSTherm drv(*_ow);
    Placeholder<DSTherm::Scratchpad> scrpd;
    if (drv.readScratchpad(_ids[index], scrpd) != OneWireNg::EC_SUCCESS) {
        log_w("%s: readScratchpad failed for index %d", TAG, index);
        return -127.0f;
    }
    // getTemp() returns millidegrees (e.g. 20125 = 20.125 °C).
    return static_cast<float>(static_cast<DSTherm::Scratchpad&>(scrpd).getTemp()) / 1000.0f;
}
