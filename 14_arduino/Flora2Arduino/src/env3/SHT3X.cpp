// Vendored from M5Unit-ENV/src/SHT3X.cpp (MIT License, M5Stack).
#include "SHT3X.h"

bool SHT3X::begin(TwoWire* wire, uint8_t addr, uint8_t sda, uint8_t scl,
                  long freq) {
    _i2c.begin(wire, sda, scl, freq);
    _addr = addr;
    _wire = wire;
    return _i2c.exist(_addr);
}

bool SHT3X::update() {
    unsigned int data[6];

    _wire->beginTransmission(_addr);
    _wire->write(0x2C);
    _wire->write(0x06);
    if (_wire->endTransmission() != 0) return false;

    delay(200);

    _wire->requestFrom(_addr, (uint8_t)6);
    for (int i = 0; i < 6; i++) data[i] = _wire->read();
    delay(50);

    if (_wire->available() != 0) return false;

    cTemp    = ((((data[0] * 256.0) + data[1]) * 175) / 65535.0) - 45;
    fTemp    = (cTemp * 1.8) + 32;
    humidity = ((((data[3] * 256.0) + data[4]) * 100) / 65535.0);
    return true;
}
