///////////////////////////////////////////////////////////////////////////////
// src/Tank.h
//
// Reads two level switch sensors to determine tank fill level.
//   Empty sensor  (PIN_TANK_EMPTY): HIGH = no water at empty probe
//   Low sensor    (PIN_TANK_LOW):   HIGH = no water at low-level probe
//
// MIT License — Copyright (c) 2026 Matthias Prinke
///////////////////////////////////////////////////////////////////////////////

#pragma once
#include <Arduino.h>

enum class TankStatus : uint8_t {
    OK       = 0,  ///< Water above the low sensor
    TANK_LOW = 1,  ///< Water below low sensor but not empty
    EMPTY    = 2,  ///< Water below the empty sensor
};

class Tank {
public:
    /// @param pinLow   GPIO connected to the "low level" float switch
    /// @param pinEmpty GPIO connected to the "empty" float switch
    Tank(uint8_t pinLow, uint8_t pinEmpty);

    void begin();

    TankStatus read();        ///< Read sensors and return current status
    TankStatus status() const { return _status; }

    bool isEmpty() const { return _status == TankStatus::EMPTY; }
    bool isLow()   const { return _status >= TankStatus::TANK_LOW; }

private:
    uint8_t    _pinLow;
    uint8_t    _pinEmpty;
    TankStatus _status = TankStatus::OK;
};
