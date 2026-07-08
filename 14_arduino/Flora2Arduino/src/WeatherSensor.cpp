///////////////////////////////////////////////////////////////////////////////
// src/WeatherSensor.cpp
//
// MIT License — Copyright (c) 2026 Matthias Prinke
///////////////////////////////////////////////////////////////////////////////

#include "WeatherSensor.h"

static const char* TAG = "WeatherSensor";

// Scan the I2C bus and log any device addresses seen. Wire should be
// initialised by the caller (Wire.begin()).
static void logI2CScan()
{
    log_i("%s: Scanning I2C bus for devices...", TAG);
    for (uint8_t addr = 1; addr < 127; ++addr) {
        Wire.beginTransmission(addr);
        uint8_t res = Wire.endTransmission();
        if (res == 0) {
            log_i("%s: I2C device found at 0x%02X", TAG, addr);
        }
    }
}

WeatherSensor::WeatherSensor()
{
    memset(&_data, 0, sizeof(_data));
    _ready = false;
}

bool WeatherSensor::begin(uint8_t sda, uint8_t scl)
{
    _ready = false;
#if defined(WEATHER_SENSOR_ENV3)

    // SHT30: use the fixed hardware address
    bool ok = _sht.begin(&Wire, SHT3X_I2C_ADDR, sda, scl, 400000U);
    if (!ok) {
        log_e("%s: SHT3X not found at 0x%02X", TAG, SHT3X_I2C_ADDR);
        // Dump I2C addresses for debugging
        logI2CScan();
        return false;
    }

    // QMP6988: use the fixed hardware address reported
    ok = _qmp.begin(&Wire, QMP6988_I2C_ADDR, sda, scl, 400000U);
    if (!ok) {
        log_e("%s: QMP6988 not found at 0x%02X", TAG, QMP6988_I2C_ADDR);
        logI2CScan();
        return false;
    }
    _ready = true;
    log_i("%s: ENV III (SHT30 + QMP6988) ready", TAG);
    return true;

#elif defined(WEATHER_SENSOR_BME280)

    // Wire must already be initialised (Wire.begin() called in setup()).
    // Default I2C address is 0x76; call setAddress(0x77) before begin() if needed.
    bool ok = _bme.begin(Wire);
    if (!ok) {
        log_e("%s: BME280 not found (chip ID mismatch)", TAG);
        return false;
    }
    _ready = true;
    log_i("%s: BME280 ready", TAG);
    return true;

#else
    log_w("%s: No weather sensor compiled in", TAG);
    return false;
#endif
}

bool WeatherSensor::read()
{
    if (!_ready) {
        _data.valid = false;
        return false;
    }

#if defined(WEATHER_SENSOR_ENV3)

    for (uint8_t attempt = 1; attempt <= WEATHER_READ_RETRIES; ++attempt) {
        bool okSht = _sht.update();
        bool okQmp = _qmp.update();

        if (okSht && okQmp) {
            _data.temperature = _sht.cTemp;
            _data.humidity    = _sht.humidity;
            _data.pressure    = _qmp.pressure / 100.0f;  // Pa → hPa
            _data.valid       = true;

            if (attempt > 1) {
                log_w("%s: Sensor read recovered on attempt %u/%u",
                      TAG,
                      (unsigned)attempt,
                      (unsigned)WEATHER_READ_RETRIES);
            }

            log_i("%s: T=%.1f°C H=%.1f%% P=%.1f hPa",
                  TAG, _data.temperature, _data.humidity, _data.pressure);
            return true;
        }

        log_w("%s: Sensor read failed (attempt %u/%u, sht=%d qmp=%d)",
              TAG,
              (unsigned)attempt,
              (unsigned)WEATHER_READ_RETRIES,
              okSht ? 1 : 0,
              okQmp ? 1 : 0);

        if (attempt < WEATHER_READ_RETRIES) {
            delay(WEATHER_READ_RETRY_DELAY_MS);
        }
    }

    _data.valid = false;
    log_e("%s: Sensor read failed after %u attempts", TAG, (unsigned)WEATHER_READ_RETRIES);
    return false;

#elif defined(WEATHER_SENSOR_BME280)

    _bme.startMeasurement();
    while (_bme.isMeasuring()) delay(1);  // typically < 10 ms at default oversampling
    _data.temperature = _bme.getTemperature() / 100.0f;   // centideg → °C
    _data.pressure    = _bme.getPressure()    / 100.0f;   // Pa → hPa
    _data.humidity    = _bme.getHumidity()    / 1024.0f;  // raw → %RH
    _data.valid = true;
    log_i("%s: T=%.1f°C H=%.1f%% P=%.1f hPa",
          TAG, _data.temperature, _data.humidity, _data.pressure);
    return true;

#else
    _data.valid = false;
    return false;
#endif
}
