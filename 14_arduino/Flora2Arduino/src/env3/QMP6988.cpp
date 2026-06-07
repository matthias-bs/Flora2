// Vendored from M5Unit-ENV/src/QMP6988.cpp (MIT License, M5Stack).
#include <math.h>
#include "stdint.h"
#include "stdio.h"
#include "QMP6988.h"

#define QMP6988_LOG(format...)
#define QMP6988_ERR(format...)

int QMP6988::getCalibrationData() {
    int status = 0;
    uint8_t a_data_uint8_tr[QMP6988_CALIBRATION_DATA_LENGTH] = {0};
    int len;

    for (len = 0; len < QMP6988_CALIBRATION_DATA_LENGTH; len += 1) {
        status = _i2c.readBytes(_addr, QMP6988_CALIBRATION_DATA_START + len,
                                &a_data_uint8_tr[len], 1);
        if (status == 0) {
            QMP6988_LOG("qmp6988 read 0xA0 error!");
            return status;
        }
    }

    qmp6988.qmp6988_cali.COE_a0 =
        (QMP6988_S32_t)(((a_data_uint8_tr[18] << SHIFT_LEFT_12_POSITION) |
                         (a_data_uint8_tr[19] << SHIFT_LEFT_4_POSITION) |
                         (a_data_uint8_tr[24] & 0x0f))
                        << 12);
    qmp6988.qmp6988_cali.COE_a0 = qmp6988.qmp6988_cali.COE_a0 >> 12;

    qmp6988.qmp6988_cali.COE_a1 =
        (QMP6988_S16_t)(((a_data_uint8_tr[20]) << SHIFT_LEFT_8_POSITION) |
                        a_data_uint8_tr[21]);
    qmp6988.qmp6988_cali.COE_a2 =
        (QMP6988_S16_t)(((a_data_uint8_tr[22]) << SHIFT_LEFT_8_POSITION) |
                        a_data_uint8_tr[23]);

    qmp6988.qmp6988_cali.COE_b00 =
        (QMP6988_S32_t)(((a_data_uint8_tr[0] << SHIFT_LEFT_12_POSITION) |
                         (a_data_uint8_tr[1] << SHIFT_LEFT_4_POSITION) |
                         ((a_data_uint8_tr[24] & 0xf0) >>
                          SHIFT_RIGHT_4_POSITION))
                        << 12);
    qmp6988.qmp6988_cali.COE_b00 = qmp6988.qmp6988_cali.COE_b00 >> 12;

    qmp6988.qmp6988_cali.COE_bt1 =
        (QMP6988_S16_t)(((a_data_uint8_tr[2]) << SHIFT_LEFT_8_POSITION) |
                        a_data_uint8_tr[3]);
    qmp6988.qmp6988_cali.COE_bt2 =
        (QMP6988_S16_t)(((a_data_uint8_tr[4]) << SHIFT_LEFT_8_POSITION) |
                        a_data_uint8_tr[5]);
    qmp6988.qmp6988_cali.COE_bp1 =
        (QMP6988_S16_t)(((a_data_uint8_tr[6]) << SHIFT_LEFT_8_POSITION) |
                        a_data_uint8_tr[7]);
    qmp6988.qmp6988_cali.COE_b11 =
        (QMP6988_S16_t)(((a_data_uint8_tr[8]) << SHIFT_LEFT_8_POSITION) |
                        a_data_uint8_tr[9]);
    qmp6988.qmp6988_cali.COE_bp2 =
        (QMP6988_S16_t)(((a_data_uint8_tr[10]) << SHIFT_LEFT_8_POSITION) |
                        a_data_uint8_tr[11]);
    qmp6988.qmp6988_cali.COE_b12 =
        (QMP6988_S16_t)(((a_data_uint8_tr[12]) << SHIFT_LEFT_8_POSITION) |
                        a_data_uint8_tr[13]);
    qmp6988.qmp6988_cali.COE_b21 =
        (QMP6988_S16_t)(((a_data_uint8_tr[14]) << SHIFT_LEFT_8_POSITION) |
                        a_data_uint8_tr[15]);
    qmp6988.qmp6988_cali.COE_bp3 =
        (QMP6988_S16_t)(((a_data_uint8_tr[16]) << SHIFT_LEFT_8_POSITION) |
                        a_data_uint8_tr[17]);

    qmp6988.ik.a0  = qmp6988.qmp6988_cali.COE_a0;
    qmp6988.ik.b00 = qmp6988.qmp6988_cali.COE_b00;

    qmp6988.ik.a1 = 3608L * (QMP6988_S32_t)qmp6988.qmp6988_cali.COE_a1 -
                    1731677965L;
    qmp6988.ik.a2 = 16889L * (QMP6988_S32_t)qmp6988.qmp6988_cali.COE_a2 -
                    87619360L;

    qmp6988.ik.bt1 = 2982L * (QMP6988_S64_t)qmp6988.qmp6988_cali.COE_bt1 +
                     107370906L;
    qmp6988.ik.bt2 = 329854L * (QMP6988_S64_t)qmp6988.qmp6988_cali.COE_bt2 +
                     108083093L;
    qmp6988.ik.bp1 = 19923L * (QMP6988_S64_t)qmp6988.qmp6988_cali.COE_bp1 +
                     1133836764L;
    qmp6988.ik.b11 = 2406L * (QMP6988_S64_t)qmp6988.qmp6988_cali.COE_b11 +
                     118215883L;
    qmp6988.ik.bp2 = 3079L * (QMP6988_S64_t)qmp6988.qmp6988_cali.COE_bp2 -
                     181579595L;
    qmp6988.ik.b12 = 6846L * (QMP6988_S64_t)qmp6988.qmp6988_cali.COE_b12 +
                     85590281L;
    qmp6988.ik.b21 = 13836L * (QMP6988_S64_t)qmp6988.qmp6988_cali.COE_b21 +
                     79333336L;
    qmp6988.ik.bp3 = 2915L * (QMP6988_S64_t)qmp6988.qmp6988_cali.COE_bp3 +
                     157155561L;
    return 1;
}

QMP6988_S16_t QMP6988::convTx02e(qmp6988_ik_data_t* ik, QMP6988_S32_t dt) {
    QMP6988_S16_t ret;
    QMP6988_S64_t wk1, wk2;

    wk1 = ((QMP6988_S64_t)ik->a1 * (QMP6988_S64_t)dt);
    wk2 = ((QMP6988_S64_t)ik->a2 * (QMP6988_S64_t)dt) >> 14;
    wk2 = (wk2 * (QMP6988_S64_t)dt) >> 10;
    wk2 = ((wk1 + wk2) / 32767) >> 19;
    ret = (QMP6988_S16_t)((ik->a0 + wk2) >> 4);
    return ret;
}

QMP6988_S32_t QMP6988::getPressure02e(qmp6988_ik_data_t* ik, QMP6988_S32_t dp,
                                       QMP6988_S16_t tx) {
    QMP6988_S32_t ret;
    QMP6988_S64_t wk1, wk2, wk3;

    wk1 = ((QMP6988_S64_t)ik->bt1 * (QMP6988_S64_t)tx);
    wk2 = ((QMP6988_S64_t)ik->bp1 * (QMP6988_S64_t)dp) >> 5;
    wk1 += wk2;
    wk2 = ((QMP6988_S64_t)ik->bt2 * (QMP6988_S64_t)tx) >> 1;
    wk2 = (wk2 * (QMP6988_S64_t)tx) >> 8;
    wk3 = wk2;
    wk2 = ((QMP6988_S64_t)ik->b11 * (QMP6988_S64_t)tx) >> 4;
    wk2 = (wk2 * (QMP6988_S64_t)dp) >> 1;
    wk3 += wk2;
    wk2 = ((QMP6988_S64_t)ik->bp2 * (QMP6988_S64_t)dp) >> 13;
    wk2 = (wk2 * (QMP6988_S64_t)dp) >> 1;
    wk3 += wk2;
    wk1 += wk3 >> 14;
    wk2 = ((QMP6988_S64_t)ik->b12 * (QMP6988_S64_t)tx);
    wk2 = (wk2 * (QMP6988_S64_t)tx) >> 22;
    wk2 = (wk2 * (QMP6988_S64_t)dp) >> 1;
    wk3 = wk2;
    wk2 = ((QMP6988_S64_t)ik->b21 * (QMP6988_S64_t)tx) >> 6;
    wk2 = (wk2 * (QMP6988_S64_t)dp) >> 23;
    wk2 = (wk2 * (QMP6988_S64_t)dp) >> 1;
    wk3 += wk2;
    wk2 = ((QMP6988_S64_t)ik->bp3 * (QMP6988_S64_t)dp) >> 12;
    wk2 = (wk2 * (QMP6988_S64_t)dp) >> 23;
    wk2 = (wk2 * (QMP6988_S64_t)dp);
    wk3 += wk2;
    wk1 += wk3 >> 15;
    wk1 /= 32767L;
    wk1 >>= 11;
    wk1 += ik->b00;
    ret = (QMP6988_S32_t)wk1;
    return ret;
}

void QMP6988::reset() {
    _i2c.writeByte(_addr, QMP6988_RESET_REG, 0xe6);
    delay(20);
    _i2c.writeByte(_addr, QMP6988_RESET_REG, 0x00);
}

void QMP6988::setpPowermode(int power_mode) {
    uint8_t data;
    qmp6988.power_mode = power_mode;
    _i2c.readBytes(_addr, QMP6988_CTRLMEAS_REG, &data, 1);
    data = data & 0xfc;
    if (power_mode == QMP6988_SLEEP_MODE)       data |= 0x00;
    else if (power_mode == QMP6988_FORCED_MODE) data |= 0x01;
    else if (power_mode == QMP6988_NORMAL_MODE) data |= 0x03;
    _i2c.writeByte(_addr, QMP6988_CTRLMEAS_REG, data);
    delay(20);
}

void QMP6988::setFilter(unsigned char filter) {
    _i2c.writeByte(_addr, QMP6988_CONFIG_REG, filter & 0x03);
    delay(20);
}

void QMP6988::setOversamplingP(unsigned char oversampling_p) {
    uint8_t data;
    _i2c.readBytes(_addr, QMP6988_CTRLMEAS_REG, &data, 1);
    data &= 0xe3;
    data |= (oversampling_p << 2);
    _i2c.writeByte(_addr, QMP6988_CTRLMEAS_REG, data);
    delay(20);
}

void QMP6988::setOversamplingT(unsigned char oversampling_t) {
    uint8_t data;
    _i2c.readBytes(_addr, QMP6988_CTRLMEAS_REG, &data, 1);
    data &= 0x1f;
    data |= (oversampling_t << 5);
    _i2c.writeByte(_addr, QMP6988_CTRLMEAS_REG, data);
    delay(20);
}

float QMP6988::calcAltitude(float pressure, float temp) {
    return (pow((101325 / pressure), 1 / 5.257) - 1) * (temp + 273.15) / 0.0065;
}

float QMP6988::calcPressure() {
    uint8_t err = 0;
    QMP6988_U32_t P_read, T_read;
    QMP6988_S32_t P_raw, T_raw;
    uint8_t a_data_uint8_tr[6] = {0};
    QMP6988_S32_t T_int, P_int;

    err = _i2c.readBytes(_addr, QMP6988_PRESSURE_MSB_REG, a_data_uint8_tr, 6);
    if (err == 0) return 0.0f;

    P_read = (QMP6988_U32_t)((((QMP6988_U32_t)(a_data_uint8_tr[0])) << SHIFT_LEFT_16_POSITION) |
                             (((QMP6988_U16_t)(a_data_uint8_tr[1])) << SHIFT_LEFT_8_POSITION) |
                             (a_data_uint8_tr[2]));
    P_raw  = (QMP6988_S32_t)(P_read - SUBTRACTOR);

    T_read = (QMP6988_U32_t)((((QMP6988_U32_t)(a_data_uint8_tr[3])) << SHIFT_LEFT_16_POSITION) |
                             (((QMP6988_U16_t)(a_data_uint8_tr[4])) << SHIFT_LEFT_8_POSITION) |
                             (a_data_uint8_tr[5]));
    T_raw  = (QMP6988_S32_t)(T_read - SUBTRACTOR);

    T_int               = convTx02e(&(qmp6988.ik), T_raw);
    P_int               = getPressure02e(&(qmp6988.ik), P_raw, T_int);
    qmp6988.temperature = (float)T_int / 256.0f;
    qmp6988.pressure    = (float)P_int / 16.0f;
    return qmp6988.pressure;
}

float QMP6988::calcTemperature() {
    uint8_t err = 0;
    QMP6988_U32_t P_read, T_read;
    QMP6988_S32_t P_raw, T_raw;
    uint8_t a_data_uint8_tr[6] = {0};
    QMP6988_S32_t T_int, P_int;

    err = _i2c.readBytes(_addr, QMP6988_PRESSURE_MSB_REG, a_data_uint8_tr, 6);
    if (err == 0) return 0.0f;

    P_read = (QMP6988_U32_t)((((QMP6988_U32_t)(a_data_uint8_tr[0])) << SHIFT_LEFT_16_POSITION) |
                             (((QMP6988_U16_t)(a_data_uint8_tr[1])) << SHIFT_LEFT_8_POSITION) |
                             (a_data_uint8_tr[2]));
    P_raw  = (QMP6988_S32_t)(P_read - SUBTRACTOR);

    T_read = (QMP6988_U32_t)((((QMP6988_U32_t)(a_data_uint8_tr[3])) << SHIFT_LEFT_16_POSITION) |
                             (((QMP6988_U16_t)(a_data_uint8_tr[4])) << SHIFT_LEFT_8_POSITION) |
                             (a_data_uint8_tr[5]));
    T_raw  = (QMP6988_S32_t)(T_read - SUBTRACTOR);

    T_int               = convTx02e(&(qmp6988.ik), T_raw);
    P_int               = getPressure02e(&(qmp6988.ik), P_raw, T_int);
    qmp6988.temperature = (float)T_int / 256.0f;
    qmp6988.pressure    = (float)P_int / 16.0f;
    return qmp6988.temperature;
}

bool QMP6988::begin(TwoWire* wire, uint8_t addr, uint8_t sda, uint8_t scl,
                    long freq) {
    _i2c.begin(wire, sda, scl, freq);
    _addr = addr;
    if (!_i2c.exist(_addr)) return false;
    reset();
    getCalibrationData();
    setpPowermode(QMP6988_NORMAL_MODE);
    setFilter(QMP6988_FILTERCOEFF_4);
    setOversamplingP(QMP6988_OVERSAMPLING_8X);
    setOversamplingT(QMP6988_OVERSAMPLING_1X);
    return true;
}

bool QMP6988::update() {
    pressure = calcPressure();
    cTemp    = calcTemperature();
    altitude = calcAltitude(pressure, cTemp);
    return true;
}
