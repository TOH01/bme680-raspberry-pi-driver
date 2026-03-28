#!/usr/bin/python3
import os
import signal
import sys
import time

from driver import BME680
from driver import bme680_constants
from bsec_bridge import BsecIAQ

LIB_PATH   = os.path.join(os.path.dirname(os.path.abspath(__file__)), "libbsec_wrapper.so")
STATE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bsec_state.bin")

running = True


def handle_sigint(signum, frame) -> None:
    global running
    running = False


def encode_gas_wait(duration_ms: int) -> tuple[int, int]:
    """Convert BSEC heater duration (ms) to BME680 gas_wait_x base + multiplier."""
    for multiplier_bits, multiplier_val in [
        (bme680_constants.HEATER_WAIT_MUTLIPLIER_1,  1),
        (bme680_constants.HEATER_WAIT_MUTLIPLIER_4,  4),
        (bme680_constants.HEATER_WAIT_MUTLIPLIER_16, 16),
        (bme680_constants.HEATER_WAIT_MUTLIPLIER_64, 64),
    ]:
        base = round(duration_ms / multiplier_val)
        if base <= bme680_constants.MAX_HEATER_WAIT_VALUE:
            return base, multiplier_bits
    return bme680_constants.MAX_HEATER_WAIT_VALUE, bme680_constants.HEATER_WAIT_MUTLIPLIER_64


def configure_sensor(bme680: BME680, settings: dict, ambient_temp: int) -> None:
    if settings["temperature_oversampling"] > 0:
        bme680.set_temperature_oversampling(settings["temperature_oversampling"])
    if settings["pressure_oversampling"] > 0:
        bme680.set_pressure_oversampling(settings["pressure_oversampling"])
    if settings["humidity_oversampling"] > 0:
        bme680.set_humidity_oversampling(settings["humidity_oversampling"])

    if settings["run_gas"]:
        base_ms, multiplier = encode_gas_wait(settings["heater_duration"])
        res_heat = bme680.get_res_heat_val(ambient_temp, settings["heater_temperature"])
        bme680.configure_heater_profile(0, base_ms, multiplier, res_heat)
        bme680.activate_heater_profile(0)
        bme680.activate_gas_conversion()


if __name__ == "__main__":
    signal.signal(signal.SIGINT, handle_sigint)

    with BME680() as bme680:
        bsec = BsecIAQ(lib_path=LIB_PATH)
        bsec.start_bsec()
        bsec.load_state(STATE_PATH)

        last_temp = 25
        last_save_ts = time.monotonic()

        while running:
            settings = bsec.get_sensor_settings()

            if not settings["trigger_measurement"]:
                time.sleep(0.1)
                continue

            configure_sensor(bme680, settings, last_temp)
            bme680.set_forced_mode()

            if not bme680.wait_for_tph_measurement():
                print("Warning: no valid TPH data, skipping")
                continue

            tph = bme680.get_compensated_tph()

            gas_res = 0.0
            if settings["run_gas"]:
                if bme680.wait_for_gas_measurement():
                    gas_res = bme680.get_gas_res()["gas_res"]
                else:
                    print("Warning: no valid gas data")

            result = bsec.compute(
                tph["temperature"],
                tph["humidity"],
                tph["pressure"],
                gas_res,
            )

            if result is None:
                continue

            last_temp = int(tph["temperature"])

            print(
                f"Raw Temp: {tph['temperature']:.2f} °C  "
                f"Raw Press: {tph['pressure']:.2f} Pa  "
                f"Raw Hum: {tph['humidity']:.2f} %  "
                f"Comp Temp: {result['temperature']:.2f} °C  "
                f"Comp Hum: {result['humidity']:.2f} %  "
                f"IAQ: {result['iaq']:.1f}  "
                f"sIAQ: {result['static_iaq']:.1f}  "
                f"CO2: {result['co2_equivalent']:.1f} ppm  "
                f"bVOC: {result['breath_voc_equivalent']:.3f} ppm  "
                f"Gas%: {result['gas_percentage']:.1f}  "
                f"CompGas: {result['compensated_gas']:.1f}  "
                f"Stab: {result['stabStatus']:.0f}  "
                f"RunIn: {result['runInStatus']:.0f}  "
                f"Accuracy: {result['iaq_accuracy']}"
            )

            if time.monotonic() - last_save_ts >= 300:
                bsec.save_state(STATE_PATH)
                last_save_ts = time.monotonic()

            # Sleep until BSEC wants the next measurement
            now_ns = time.monotonic_ns()
            wait_ns = settings["next_call_ns"] - now_ns
            if wait_ns > 0:
                time.sleep(wait_ns / 1_000_000_000)

        print("\nShutting down, saving BSEC state...")
        bsec.save_state(STATE_PATH)
        print(f"State saved to {STATE_PATH}")

    sys.exit(0)
