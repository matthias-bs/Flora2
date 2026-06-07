///////////////////////////////////////////////////////////////////////////////
// src/Irrigation.h
//
// Automatic and manual irrigation logic.
//
// autoIrrigate() decides per-pump whether to irrigate based on:
//   • Plant sensor readings (moisture, light intensity)
//   • Night window suppression
//   • Minimum rest period between irrigations
//   • Tank water level
//
// MIT License — Copyright (c) 2026 Matthias Prinke
///////////////////////////////////////////////////////////////////////////////

#pragma once
#include <Arduino.h>
#include <functional>
#include "ConfigLoader.h"
#include "Pump.h"
#include "Tank.h"

/// Result of one auto-irrigation decision per pump.
struct IrrigationDecision {
    bool should_irrigate;  ///< Conditions met
    bool scheduled;        ///< True if rest-period not expired (defer to next cycle)
    bool ran;              ///< True if pump was actually activated this cycle
    PumpResult result;     ///< Pump run result (meaningful when ran == true)
};

class Irrigation {
public:
    /// @param loopCb  Called every ~60 s during long pump runs to keep MQTT alive
    explicit Irrigation(std::function<void()> loopCb = nullptr);

    /// Auto-irrigation pass.
    /// @param cfg         Application config
    /// @param sensorData  Plant sensor readings (indices match cfg.plants[])
    /// @param pumps       Array of Pump objects (indexed 0-based)
    /// @param numPumps    Length of pumps array (usually NUM_PUMPS)
    /// @param tank        Tank object (read before each pump run)
    /// @param pumpLastRun Timestamps of last pump run — updated on success (RTC_DATA_ATTR)
    /// @param decisions   Output: one entry per pump
    void autoIrrigate(const AppConfig&        cfg,
                      const PlantSensorData*  sensorData,
                      Pump*                   pumps,
                      uint8_t                 numPumps,
                      Tank&                   tank,
                      time_t*                 pumpLastRun,
                      IrrigationDecision*     decisions);

    /// Manual irrigation for a single pump.
    /// @param pumpIdx   0-based pump index
    /// @param durationS Run duration in seconds
    /// @param pump      Pump to activate
    /// @param tank      Tank reference
    /// @param lastRun   Timestamp updated on success
    /// @return Pump run result
    PumpResult manualIrrigate(uint8_t                pumpIdx,
                              uint32_t               durationS,
                              Pump&                  pump,
                              Tank&                  tank,
                              time_t&                lastRun);

private:
    std::function<void()> _loopCb;
    static const uint32_t KEEPALIVE_MS = 60000;

    bool isNightTime(const GeneralConfig& g) const;
    bool restExpired(time_t lastRun, uint32_t restSec) const;
};
