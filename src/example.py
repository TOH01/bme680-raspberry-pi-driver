#!/usr/bin/python3
import os
import signal
import sys
import time

from driver import BME680
from driver import bme680_constants
from bsec_bridge import BsecIAQ

LIB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "libbsec_wrapper.so")
STATE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "bsec_state.bin")
INTERVAL_S = 3
TARGET_TEMP = 200
AMBIENT_TEMP_FALLBACK = 25

running = True


def handle_sigint(signum, frame) -> None:
    global running
    running = False


def configure_heater(bme680: BME680, ambient_temp: int) -> None:
    res_heat_val = bme680.get_res_heat_val(ambient_temp, TARGET_TEMP)
    bme680.configure_heater_profile(
        0, 25,
        bme680_constants.HEATER_WAIT_MUTLIPLIER_4,
        res_heat_val,
    )


if __name__ == "__main__":
    signal.signal(signal.SIGINT, handle_sigint)

    with BME680() as bme680:
        bsec_iaq = BsecIAQ(lib_path=LIB_PATH)
        bsec_iaq.start_bsec()
        bsec_iaq.load_state(STATE_PATH)

        bme680.activate_heater_profile(0)
        bme680.activate_gas_conversion()

        last_temp = AMBIENT_TEMP_FALLBACK
        last_save_ts = time.monotonic()

        while running:
            loop_start = time.monotonic()

            configure_heater(bme680, last_temp)
            bme680.set_forced_mode()

            if not bme680.wait_for_tph_measurement():
                print("Warning: no valid TPH data, skipping")
                time.sleep(INTERVAL_S)
                continue

            tph = bme680.get_compensated_tph()

            if not bme680.wait_for_gas_measurement():
                print("Warning: no valid gas data, skipping")
                time.sleep(INTERVAL_S)
                continue

            gas = bme680.get_gas_res()
            bsec = bsec_iaq.compute(tph["temperature"], tph["humidity"],
                                    gas["gas_res"])

            if bsec is None:
                print("BSEC not ready, skipping")
                time.sleep(INTERVAL_S)
                continue

            last_temp = int(tph["temperature"])

            print(f"Temp: {tph['temperature']:.2f} °C  "
                  f"Press: {tph['pressure']:.2f} Pa  "
                  f"Hum: {tph['humidity']:.2f} %  "
                  f"IAQ: {bsec['iaq']:.1f}  "
                  f"Accuracy: {bsec['accuracy']}")

            if time.monotonic() - last_save_ts >= 300:
                bsec_iaq.save_state(STATE_PATH)
                last_save_ts = time.monotonic()

            elapsed = time.monotonic() - loop_start
            time.sleep(max(0, INTERVAL_S - elapsed))

        print("\nShutting down, saving BSEC state...")
        bsec_iaq.save_state(STATE_PATH)
        print(f"State saved to {STATE_PATH}")

    sys.exit(0)
