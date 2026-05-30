#!/usr/bin/python3
import time

from driver import BME680, bme680_constants

if __name__ == "__main__":
    bme680 = BME680()
    
    bme680.soft_reset()
    time.sleep(0.1)
    
    bme680.activate_gas_conversion()

    last_temp = bme680_constants.DEFAULT_INITIAL_GAS_AMB_TEMP

    while True:
        bme680.configure_default_heater(last_temp)
        bme680.configure_default_oversampling()
        bme680.set_forced_mode()

        if not bme680.wait_for_tph_measurement():
            print("Warning: no valid TPH data, skipping")
            continue

        tph = bme680.get_compensated_tph()

        if not bme680.wait_for_gas_measurement():
            print("Warning: no valid gas data, skipping")
            continue

        gas_res = bme680.get_gas_res()

        print(f"Raw Temp: {tph['temperature']:.2f} °C  "
              f"Raw Press: {tph['pressure']:.2f} Pa  "
              f"Raw Hum: {tph['humidity']:.2f} %  "
              f"Raw Gas Res: {gas_res:.2f} Ohm")

        time.sleep(3)
