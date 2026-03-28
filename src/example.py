#!/usr/bin/python3
import time

from driver import BME680
from driver import bme680_constants

INTERVAL_S = 3
TARGET_TEMP = 200
AMBIENT_TEMP_FALLBACK = 25


def configure_heater(bme680: BME680, ambient_temp: int) -> None:
    res_heat_val = bme680._get_res_heat_val_(
        ambient_temp,
        bme680_constants.DEFAULT_HEATER_TARGET_TEMP
    )

    bme680.configure_heater_profile(
        bme680_constants.DEFAULT_HEATER_PROFILE,
        bme680_constants.DEFAULT_HEATER_WAIT_MS,
        bme680_constants.HEATER_WAIT_MUTLIPLIER_4,
        res_heat_val,
    )


if __name__ == "__main__":
    with BME680() as bme680:
        bme680.activate_heater_profile(0)
        bme680.activate_gas_conversion()

        last_temp = AMBIENT_TEMP_FALLBACK

        while True:
            configure_heater(bme680, last_temp)
            bme680.set_forced_mode()

            if not bme680.wait_for_tph_measurement():
                print("Warning: no valid TPH data, skipping")
                continue

            tph = bme680.get_compensated_tph()

            if not bme680.wait_for_gas_measurement():
                print("Warning: no valid gas data, skipping")
                continue

            gas = bme680.get_gas_res()

            print(f"Raw Temp: {tph['temperature']:.2f} °C  "
                  f"Raw Press: {tph['pressure']:.2f} Pa  "
                  f"Raw Hum: {tph['humidity']:.2f} %  "
                  f"Raw Gas Res: {gas['gas_res']:.2f} Ohm")

            time.sleep(INTERVAL_S)
