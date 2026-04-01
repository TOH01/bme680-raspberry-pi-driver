#!/usr/bin/python3
import argparse
import json
import os
import tempfile
from pathlib import Path

from bsec_bridge import BsecIAQ
from datalogger import DataLogger
from driver import BME680

_DIR = Path(__file__).parent
LIB = _DIR / "libbsec_wrapper.so"
STATE = _DIR / "bsec_state.bin"
LOG = _DIR / "airquality.bin"
LATEST = _DIR / "latest.json"


def _write_latest(result: dict) -> None:
    try:
        fd, tmp = tempfile.mkstemp(dir=_DIR, suffix=".tmp")
        with os.fdopen(fd, "w") as f:
            json.dump(result, f)
        os.replace(tmp, LATEST)
    except OSError:
        pass


def main() -> None:
    parser = argparse.ArgumentParser(description="BME680 air-quality sensor daemon")
    parser.add_argument(
        "--log-interval", "-i",
        type=int, default=30,
        help="Binary log interval in seconds (default: 30)",
    )
    args = parser.parse_args()

    logger = DataLogger(LOG, interval=args.log_interval)
    bme = BME680()
    bsec = BsecIAQ(lib_path=LIB)

    def on_result(result: dict) -> None:
        _write_latest(result)

        if result["iaq_accuracy"] > 2:
            logger.maybe_log(
                result["temperature"],
                result["humidity"],
                result["iaq"],
                result["co2_equivalent"],
            )

    print(f"[sensor] starting — logging every {args.log_interval}s to {LOG}")

    try:
        bsec.run(bme, on_result, state_path=STATE)
    except KeyboardInterrupt:
        print("[sensor] interrupted, saving BSEC state")
        bsec.save_state(STATE)
    finally:
        bme.close()


if __name__ == "__main__":
    main()
