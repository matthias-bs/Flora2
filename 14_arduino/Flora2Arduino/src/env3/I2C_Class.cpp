// Vendored from M5Unit-ENV/src/I2C_Class.cpp (MIT License, M5Stack).
// Modified: begin() no longer calls Wire.end()/Wire.begin() — Wire is already
// initialised in setup() before any sensor is used.
#include "I2C_Class.h"

void I2C_Class::begin(TwoWire* wire, uint8_t sda, uint8_t scl, long freq) {
    _wire = wire;
    _sda  = sda;
    _scl  = scl;
    _freq = freq;
    // Wire.end() / Wire.begin() intentionally omitted: the caller (WeatherSensor)
    // runs Wire.begin(SDA, SCL) in setup() before calling sensor begin().
}

bool I2C_Class::exist(uint8_t addr) {
    _wire->beginTransmission(addr);
    return (_wire->endTransmission() == 0);
}

bool I2C_Class::writeBytes(uint8_t addr, uint8_t reg, uint8_t* buffer,
                            uint8_t length) {
    _wire->beginTransmission(addr);
    _wire->write(reg);
    _wire->write(buffer, length);
    return (_wire->endTransmission() == 0);
}

bool I2C_Class::readBytes(uint8_t addr, uint8_t reg, uint8_t* buffer,
                           uint8_t length) {
    _wire->beginTransmission(addr);
    _wire->write(reg);
    _wire->endTransmission();
    if (_wire->requestFrom(addr, length)) {
        for (uint8_t i = 0; i < length; i++) buffer[i] = _wire->read();
        return true;
    }
    return false;
}

bool I2C_Class::readU16(uint8_t addr, uint8_t reg_addr, uint16_t* value) {
    uint8_t buf[2] = {0, 0};
    bool r = readBytes(addr, reg_addr, buf, 2);
    *value = (buf[0] << 8) | buf[1];
    return r;
}

bool I2C_Class::writeU16(uint8_t addr, uint8_t reg_addr, uint16_t value) {
    uint8_t buf[2] = { (uint8_t)(value >> 8), (uint8_t)(value & 0xff) };
    return writeBytes(addr, reg_addr, buf, 2);
}

bool I2C_Class::writeByte(uint8_t addr, uint8_t reg, uint8_t data) {
    _wire->beginTransmission(addr);
    _wire->write(reg);
    _wire->write(data);
    return (_wire->endTransmission() == 0);
}

uint8_t I2C_Class::readByte(uint8_t addr, uint8_t reg) {
    _wire->beginTransmission(addr);
    _wire->write(reg);
    _wire->endTransmission();
    if (_wire->requestFrom(addr, (uint8_t)1)) return _wire->read();
    return 0;
}

bool I2C_Class::writeBitOn(uint8_t addr, uint8_t reg, uint8_t data) {
    uint8_t val = readByte(addr, reg);
    return writeByte(addr, reg, val | data);
}

bool I2C_Class::writeBitOff(uint8_t addr, uint8_t reg, uint8_t data) {
    uint8_t val = readByte(addr, reg);
    return writeByte(addr, reg, val & ~data);
}
