///////////////////////////////////////////////////////////////////////////////
// src/DS1820.h
//
// DS18B20 / DS18S20 OneWire temperature sensor driver.
// Uses pstolarz/OneWireNg (OneWireNg_CurrentPlatform + DSTherm driver).
//
// The OneWireNg object must NOT be constructed globally (platform setup is
// performed in its constructor).  A Placeholder<> provides aligned storage
// for the object; actual construction happens inside begin().
//
// MIT License — Copyright (c) 2026 Matthias Prinke
///////////////////////////////////////////////////////////////////////////////

#pragma once
#include <Arduino.h>
#include <OneWireNg_CurrentPlatform.h>
#include <drivers/DSTherm.h>

/// Maximum number of DS18xx sensors supported on one bus.
#define DS1820_MAX_DEVICES  4

class DS1820 {
public:
    /// @param pin  GPIO connected to the OneWire bus (with 4.7 kΩ pull-up)
    explicit DS1820(uint8_t pin);

    /// Initialise the bus and enumerate attached DS18xx devices.
    /// Must be called from setup() — not safe as a global constructor.
    /// Returns true if at least one device is found.
    bool begin();

    /// Request temperature conversion from all sensors (blocking, ≤ 750 ms).
    void requestAll();

    /// Get temperature from device at index (call requestAll() first).
    /// Returns -127.0 on error or out-of-range index.
    float getTemperatureC(uint8_t index) const;

    uint8_t getDeviceCount() const { return _count; }

private:
    uint8_t                                _pin;
    OneWireNg_CurrentPlatform*             _ow = nullptr;
    OneWireNg::Id                          _ids[DS1820_MAX_DEVICES];
    uint8_t                                _count = 0;
};
