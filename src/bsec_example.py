#!/usr/bin/python3
from pathlib import Path

from bsec_bridge import BsecIAQ
from driver import BME680

_DIR = Path(__file__).parent
LIB_PATH = _DIR / "libbsec_wrapper.so"
STATE_PATH = _DIR / "bsec_state.bin"


def print_result(result):
    print(
        f"Temp: {result['temperature']:.2f} °C  "
        f"Hum: {result['humidity']:.2f} %  "
        f"IAQ: {result['iaq']:.1f}  "
        f"sIAQ: {result['static_iaq']:.1f}  "
        f"CO2: {result['co2_equivalent']:.1f} ppm  "
        f"bVOC: {result['breath_voc_equivalent']:.3f} ppm  "
        f"Gas%: {result['gas_percentage']:.1f}  "
        f"Acc: {result['iaq_accuracy']}  "
        f"Stab: {result['stab_status']:.0f}  "
        f"RunIn: {result['run_in_status']:.0f}",
    )


if __name__ == "__main__":
    bme680 = BME680()
    bsec = BsecIAQ(lib_path=LIB_PATH)

    try:
        bsec.run(bme680, callback=print_result, state_path=STATE_PATH)
    except KeyboardInterrupt:
        bsec.save_state(STATE_PATH)
    finally:
        bme680.close()
