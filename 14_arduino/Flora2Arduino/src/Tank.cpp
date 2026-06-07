///////////////////////////////////////////////////////////////////////////////
// src/Tank.cpp
//
// MIT License — Copyright (c) 2026 Matthias Prinke
///////////////////////////////////////////////////////////////////////////////

#include "Tank.h"

Tank::Tank(uint8_t pinLow, uint8_t pinEmpty)
    : _pinLow(pinLow), _pinEmpty(pinEmpty)
{}

void Tank::begin()
{
    pinMode(_pinLow,   INPUT);
    pinMode(_pinEmpty, INPUT);
}

TankStatus Tank::read()
{
    bool low   = (digitalRead(_pinLow)   == HIGH);
    bool empty = (digitalRead(_pinEmpty) == HIGH);

    if (empty) {
        _status = TankStatus::EMPTY;
    } else if (low) {
        _status = TankStatus::TANK_LOW;
    } else {
        _status = TankStatus::OK;
    }
    return _status;
}
