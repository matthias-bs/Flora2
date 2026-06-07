///////////////////////////////////////////////////////////////////////////////
// src/MiFloraSensor.cpp
//
// MIT License — Copyright (c) 2026 Matthias Prinke
///////////////////////////////////////////////////////////////////////////////

#include "MiFloraSensor.h"
#include <NimBLEDevice.h>
#include <Preferences.h>
#include <algorithm>

static const char* TAG = "MiFlora";

MiFloraSensor::MiFloraSensor() {}

void MiFloraSensor::readBattery(const std::vector<std::string>& addresses,
                                 PlantSensorData*               data,
                                 uint8_t                        numSensors)
{
    if (!NimBLEDevice::isInitialized()) {
        NimBLEDevice::init("Flora2");
    }

    Preferences prefs;
    prefs.begin("mf_batt", false);  // "mf_batt" NVS namespace

    for (uint8_t i = 0; i < numSensors && i < (uint8_t)addresses.size(); i++) {
        const std::string& addr = addresses[i];
        if (addr.empty()) continue;

        log_i("%s: Connecting to %s for GATT read", TAG, addr.c_str());

        NimBLEClient* pClient = NimBLEDevice::createClient();
        if (!pClient) continue;

        bool connected = pClient->connect(NimBLEAddress(addr, BLE_ADDR_PUBLIC), false);
        if (!connected) {
            log_w("%s: Connection to %s failed", TAG, addr.c_str());
            NimBLEDevice::deleteClient(pClient);
            continue;
        }

        // In direct-GATT mode, export link RSSI through MQTT payload.
        data[i].rssi = pClient->getRssi();

        uint8_t battPct = 0;
        bool    gotGattData = false;

        NimBLERemoteService* pSvc = pClient->getService(MIFLORA_SVC_UUID);
        if (pSvc) {
            // MicroPython sequence equivalent:
            //   write 0xA0 0x1F to char 1a00, then read char 1a01.
            NimBLERemoteCharacteristic* pCtrl = pSvc->getCharacteristic(MIFLORA_CTRL_CHAR);
            NimBLERemoteCharacteristic* pData = pSvc->getCharacteristic(MIFLORA_DATA_CHAR);

            if (pCtrl && pData && pData->canRead()) {
                uint8_t cmd[2] = {0xA0, 0x1F};
                bool modeOk = false;
                if (pCtrl->canWrite()) {
                    modeOk = pCtrl->writeValue(cmd, sizeof(cmd), true);
                } else if (pCtrl->canWriteNoResponse()) {
                    modeOk = pCtrl->writeValue(cmd, sizeof(cmd), false);
                }

                if (modeOk) {
                    delay(120);
                    NimBLEAttValue v = pData->readValue();
                    if (v.size() >= 10) {
                        const uint8_t* b = v.data();
                        int16_t tempRaw = (int16_t)((b[1] << 8) | b[0]);
                        uint32_t light  = ((uint32_t)b[3]) |
                                          ((uint32_t)b[4] << 8) |
                                          ((uint32_t)b[5] << 16) |
                                          ((uint32_t)b[6] << 24);
                        uint8_t moist   = b[7];
                        int16_t cond    = (int16_t)((b[9] << 8) | b[8]);

                        data[i].temperature  = (float)tempRaw / 10.0f;
                        data[i].moisture     = moist;
                        data[i].lux          = light;
                        data[i].conductivity = (uint16_t)cond;
                        data[i].valid_mask  |= (MIFLORA_VALID_TEMP |
                                                MIFLORA_VALID_MOI  |
                                                MIFLORA_VALID_LUX  |
                                                MIFLORA_VALID_FER);
                        data[i].valid        = true;
                        data[i].last_update  = time(nullptr);
                        gotGattData = true;

                        // Refresh RSSI after data transfer to better reflect link quality.
                        data[i].rssi = pClient->getRssi();

                        log_i("%s: Sensor[%d] GATT T=%.1f moi=%u lux=%lu fer=%d rssi=%d",
                              TAG, i, data[i].temperature, data[i].moisture,
                            (unsigned long)data[i].lux, data[i].conductivity,
                            data[i].rssi);
                    }
                }
            }

            NimBLERemoteCharacteristic* pChar = pSvc->getCharacteristic(MIFLORA_BATT_CHAR);
            if (pChar && pChar->canRead()) {
                std::string val = pChar->readValue();
                if (!val.empty()) {
                    battPct = (uint8_t)val[0];
                    log_i("%s: Sensor[%d] battery = %d%%", TAG, i, battPct);
                }
            }
        }

        pClient->disconnect();
        NimBLEDevice::deleteClient(pClient);

        // Update data and persist to NVS
        if (battPct > 0) {
            data[i].battery = battPct;
            // Use full sensor MAC address (without colons) as stable NVS key.
            std::string key = addr;
            key.erase(std::remove(key.begin(), key.end(), ':'), key.end());
            prefs.putUChar(key.c_str(), battPct);
        }

        if (!gotGattData) {
            log_w("%s: Sensor[%d] GATT sensor read unavailable this cycle", TAG, i);
        }
    }

    prefs.end();
}
