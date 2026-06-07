///////////////////////////////////////////////////////////////////////////////
// src/Irrigation.cpp
//
// MIT License — Copyright (c) 2026 Matthias Prinke
///////////////////////////////////////////////////////////////////////////////

#include "Irrigation.h"

static const char* TAG = "Irrigation";

Irrigation::Irrigation(std::function<void()> loopCb)
    : _loopCb(loopCb)
{}

// ─────────────────────────────────────────────────────────────────────────────
// Public
// ─────────────────────────────────────────────────────────────────────────────

void Irrigation::autoIrrigate(const AppConfig&        cfg,
                               const PlantSensorData*  sensorData,
                               Pump*                   pumps,
                               uint8_t                 numPumps,
                               Tank&                   tank,
                               time_t*                 pumpLastRun,
                               IrrigationDecision*     decisions)
{
    // Initialise outputs
    for (uint8_t p = 0; p < numPumps; p++) {
        decisions[p] = { false, false, false, PumpResult::OK };
    }

    if (!cfg.general.auto_irrigation) {
        log_i("%s: Auto irrigation disabled", TAG);
        return;
    }

    if (isNightTime(cfg.general)) {
        log_i("%s: Night window — skipping", TAG);
        return;
    }

    // Evaluate each pump (1-based in config, 0-based in array)
    for (uint8_t p = 0; p < numPumps; p++) {
        uint8_t pump1based = p + 1;

        bool any_below_min  = false;
        bool any_above_max  = false;
        bool any_high_light = false;
        bool any_valid      = false;

        // Evaluate per-plant thresholds for this pump; detailed text is populated in the second loop below.
        char details[256];
        details[0] = '\0';
        size_t off = 0;

        for (uint8_t s = 0; s < cfg.num_plants; s++) {
            const PlantConfig&     pc  = cfg.plants[s];
            const PlantSensorData& sd  = sensorData[s];

            if (pc.pump != pump1based) continue;
            if (!sd.valid)             continue;

            any_valid = true;

            if (sd.moisture < pc.moist_min)  any_below_min  = true;
            if (sd.moisture > pc.moist_max)  any_above_max  = true;

            // Suppress irrigation if light intensity is very high (risk of sunburn)
            if (pc.light_irr > 0 && sd.lux > 0 && sd.lux > pc.light_irr) {
                any_high_light = true;
            }
        }
        // Rebuild details buffer but include invalid sensors too for clarity
        off = 0;
        for (uint8_t s = 0; s < cfg.num_plants; s++) {
            const PlantConfig& pc = cfg.plants[s];
            if (pc.pump != pump1based) continue;
            const PlantSensorData& sd = sensorData[s];
            if (off < sizeof(details) - 1) {
                int wrote = 0;
                if (!sd.valid) {
                    wrote = snprintf(details + off, sizeof(details) - off, "%s:invalid; ", pc.id);
                } else {
                    wrote = snprintf(details + off, sizeof(details) - off, "%s:moist=%u(min=%u,max=%u); ",
                                     pc.id, sd.moisture, pc.moist_min, pc.moist_max);
                }
                if (wrote > 0) off += (size_t)wrote;
            }
        }

        if (!any_valid) {
            log_i("%s: Pump%d — no valid sensor data, skipping (%s)", TAG, pump1based, details);
            continue;
        }
        if (!any_below_min) {
            log_i("%s: Pump%d — moisture OK, no irrigation needed (%s)", TAG, pump1based, details);
            continue;
        }
        if (any_above_max) {
            log_i("%s: Pump%d — moisture at/above max, stopping (%s)", TAG, pump1based, details);
            continue;
        }
        if (any_high_light) {
            log_i("%s: Pump%d — high light intensity, suppressing irrigation (%s)", TAG, pump1based, details);
            continue;
        }

        decisions[p].should_irrigate = true;

        if (!restExpired(pumpLastRun[p], cfg.general.irr_rest)) {
            log_i("%s: Pump%d — rest period not expired, deferring", TAG, pump1based);
            decisions[p].scheduled = true;
            continue;
        }

        // All conditions met — run the pump
          log_i("%s: Pump%d — irrigating for %lu s (details: %s)",
              TAG, pump1based, cfg.general.irr_duration_auto[p], details);

        tank.read();
        if (tank.isEmpty()) {
            log_w("%s: Tank empty — skipping Pump%d", TAG, pump1based);
            continue;
        }

        decisions[p].result = pumps[p].run(
            cfg.general.irr_duration_auto[p] * 1000UL,
            tank,
            KEEPALIVE_MS,
            _loopCb
        );
        decisions[p].ran = true;

        if (decisions[p].result != PumpResult::TANK_EMPTY) {
            time_t now = time(nullptr);
            if (now < 1609459200) {
                log_w("%s: Time not synced (epoch=%ld) — not updating pump last-run", TAG, (long)now);
            } else {
                pumpLastRun[p] = now;
            }
        }
    }
}

PumpResult Irrigation::manualIrrigate(uint8_t   pumpIdx,
                                       uint32_t  durationS,
                                       Pump&     pump,
                                       Tank&     tank,
                                       time_t&   lastRun)
{
    log_i("%s: Manual run pump[%d] for %lu s", TAG, pumpIdx, durationS);
    tank.read();
    if (tank.isEmpty()) {
        log_w("%s: Tank empty — refusing manual irrigation", TAG);
        return PumpResult::TANK_EMPTY;
    }

    PumpResult res = pump.run(durationS * 1000UL, tank, KEEPALIVE_MS, _loopCb);
    if (res != PumpResult::TANK_EMPTY) {
        time_t now = time(nullptr);
        if (now < 1609459200) {
            log_w("%s: Time not synced (epoch=%ld) — not updating manual pump last-run", TAG, (long)now);
        } else {
            lastRun = now;
        }
    }
    return res;
}

// ─────────────────────────────────────────────────────────────────────────────
// Private
// ─────────────────────────────────────────────────────────────────────────────

bool Irrigation::isNightTime(const GeneralConfig& g) const
{
    time_t now = time(nullptr);
    // Guard against unsynced RTC/NTP time (epoch near 1970).
    // In this case, do not suppress irrigation by night-window logic.
    if (now < 1609459200) { // 2021-01-01 00:00:00 UTC
        log_w("%s: Time not synced (epoch=%ld) — ignoring night window", TAG, (long)now);
        return false;
    }

    struct tm tmbuf;
    struct tm* t = localtime_r(&now, &tmbuf);
    if (!t) {
        log_w("%s: localtime conversion failed — ignoring night window", TAG);
        return false;
    }

    int cur  = t->tm_hour * 60 + t->tm_min;
    int beg  = g.night_begin_hr * 60 + g.night_begin_min;
    int end  = g.night_end_hr   * 60 + g.night_end_min;

    bool isNight = false;
    if (beg > end) {
        // Night crosses midnight: e.g. 22:00 → 07:00
        isNight = (cur >= beg || cur < end);
    } else {
        isNight = (cur >= beg && cur < end);
    }

    char nowBuf[32];
    strftime(nowBuf, sizeof(nowBuf), "%Y-%m-%d %H:%M:%S", t);
    log_i("%s: Night check now=%s window=%02u:%02u-%02u:%02u => %s",
          TAG,
          nowBuf,
          g.night_begin_hr, g.night_begin_min,
          g.night_end_hr, g.night_end_min,
          isNight ? "night" : "day");

    return isNight;
}

bool Irrigation::restExpired(time_t lastRun, uint32_t restSec) const
{
    if (lastRun == 0) return true;  // Never ran → allow immediately
    return (time(nullptr) - lastRun) >= (time_t)restSec;
}
