///////////////////////////////////////////////////////////////////////////////
// src/Pump.cpp
//
// MIT License — Copyright (c) 2026 Matthias Prinke
///////////////////////////////////////////////////////////////////////////////

#include "Pump.h"

static const char* TAG = "Pump";

Pump::Pump(uint8_t pin, uint8_t index)
    : _pin(pin), _index(index)
{}

void Pump::begin()
{
    pinMode(_pin, OUTPUT);
    off();  // Ensure pump is off at startup
}

PumpResult Pump::run(uint32_t              duration_ms,
                     Tank&                 tank,
                     uint32_t             keepalive_ms,
                     std::function<void()> loopCb)
{
    // Refuse to run if tank is already empty
    tank.read();
    if (tank.isEmpty()) {
        log_w("%s[%d]: Tank empty — refusing to run", TAG, _index);
        return PumpResult::TANK_EMPTY;
    }

    log_i("%s[%d]: Starting, duration=%lu ms", TAG, _index, duration_ms);
    on();

    unsigned long start = millis();
    unsigned long lastKeepalive = start;
    PumpResult result = PumpResult::OK;

    while ((millis() - start) < duration_ms) {
        // Keep-alive callback
        if (loopCb && keepalive_ms > 0 &&
            (millis() - lastKeepalive) >= keepalive_ms)
        {
            loopCb();
            lastKeepalive = millis();
        }

        // Abort on empty tank
        if ((millis() - start) % 2000 < 100) {  // Check every ~2 s
            tank.read();
            if (tank.isEmpty()) {
                log_w("%s[%d]: Tank went empty during run — stopping", TAG, _index);
                result = PumpResult::TANK_EMPTY;
                break;
            }
            if (tank.isLow()) {
                result = PumpResult::TANK_LOW;  // Don't break, let it finish normally
            }
        }

        delay(100);
    }

    off();
    log_i("%s[%d]: Stopped (result=%d)", TAG, _index, (int)result);
    return result;
}

void Pump::on()
{
    _running = true;
    digitalWrite(_pin, HIGH);
}

void Pump::off()
{
    _running = false;
    digitalWrite(_pin, LOW);
}
