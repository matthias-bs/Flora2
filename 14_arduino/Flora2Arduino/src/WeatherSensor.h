///////////////////////////////////////////////////////////////////////////////
// src/WeatherSensor.h
//
// Reads ambient weather data from an attached sensor.
// Select sensor type via Flora2Cfg.h feature flag:
//   WEATHER_SENSOR_ENV3  — M5Stack ENV III: SHT30 + QMP6988
//   WEATHER_SENSOR_BME280 — Bosch BME280
//
// MIT License — Copyright (c) 2026 Matthias Prinke
///////////////////////////////////////////////////////////////////////////////

#pragma once
#include <Arduino.h>
#include <Wire.h>
#include "../Flora2Cfg.h"

#if defined(WEATHER_SENSOR_ENV3)
  // Vendored copies of SHT3X + QMP6988 from M5Unit-ENV (src/env3/).
  // Using local copies avoids the M5Unit-ENV library dependency entirely —
  // the Arduino IDE would otherwise compile unit_BME688.cpp which pulls in
  // M5UnitComponent.hpp, bme68xLibrary.h, and identify_functions.hpp.
  #include "env3/SHT3X.h"
  #include "env3/QMP6988.h"
#elif defined(WEATHER_SENSOR_BME280)
  #include <pocketBME280.h>
#endif

class WeatherSensor {
public:
    WeatherSensor();

    /// Initialise the sensor. Wire must be started before calling.
    /// Returns true if the sensor is detected and ready.
    bool begin(uint8_t sda = PIN_I2C_SDA, uint8_t scl = PIN_I2C_SCL);

    /// Read all channels. Fills the internal WeatherData struct.
    /// Returns true on success.
    bool read();

    /// True after a successful begin().
    bool isReady() const { return _ready; }

    const WeatherData& data() const { return _data; }

private:
    WeatherData _data;
  bool        _ready = false;

#if defined(WEATHER_SENSOR_ENV3)
    SHT3X   _sht;
    QMP6988 _qmp;
#elif defined(WEATHER_SENSOR_BME280)
    pocketBME280 _bme;
#endif
};
