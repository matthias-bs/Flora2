///////////////////////////////////////////////////////////////////////////////
// src/Pump.h
//
// Controls a single pump via a GPIO output.
// Runs for a specified duration while optionally calling a keep-alive
// callback (e.g. mqtt.loop()) at regular intervals to maintain connections.
//
// MIT License — Copyright (c) 2026 Matthias Prinke
///////////////////////////////////////////////////////////////////////////////

#pragma once
#include <Arduino.h>
#include <functional>
#include "Tank.h"

enum class PumpResult : uint8_t {
    OK          = 0,  ///< Completed full run
    TANK_EMPTY  = 1,  ///< Aborted — tank empty during run
    TANK_LOW    = 2,  ///< Completed but tank reached low level
};

class Pump {
public:
    /// @param pin        GPIO pin (HIGH = pump on)
    /// @param index      0-based pump index (for logging)
    Pump(uint8_t pin, uint8_t index);

    void begin();

    /// Run pump for duration_ms milliseconds.
    /// @param duration_ms    Run time in milliseconds
    /// @param tank           Tank reference — aborts if isEmpty() becomes true
    /// @param keepalive_ms   Call loopCb every this many ms (0 = never)
    /// @param loopCb         Optional function called for keep-alive (e.g. mqtt.loop)
    /// @return PumpResult
    PumpResult run(uint32_t              duration_ms,
                   Tank&                 tank,
                   uint32_t             keepalive_ms = 0,
                   std::function<void()> loopCb      = nullptr);

    bool isRunning() const { return _running; }

private:
    void on();
    void off();

    uint8_t _pin;
    uint8_t _index;
    bool    _running = false;
};
