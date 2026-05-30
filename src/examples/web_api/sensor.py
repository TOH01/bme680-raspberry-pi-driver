import argparse
import json
import os
import tempfile
import time
from pathlib import Path

from bsec_bridge import BsecIAQ
from driver import BME680
from examples.web_api.datalogger import DataLogger

_DIR = Path(__file__).parent
LIB = _DIR.parent / "libbsec_wrapper.so"
STATE = _DIR / "bsec_state.bin"
LOG = _DIR / "airquality.bin"
LATEST = _DIR / "latest.json"


def _write_latest(result: dict) -> None:
    try:
        fd, tmp = tempfile.mkstemp(dir=_DIR, suffix=".tmp")
        with os.fdopen(fd, "w") as f:
            json.dump(result, f)
        Path(tmp).replace(LATEST)
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

    bme.soft_reset()
    time.sleep(0.1)

    def on_result(result: dict) -> None:
        result["timestamp"] = time.time()
        _write_latest(result)
        if result.get("iaq_accuracy", 0) > 2 and result.get("run_in_status") != 0:
            logger.maybe_log(
                result["temperature"],
                result["humidity"],
                result["iaq"],
                result["co2_equivalent"],
            )

    try:
        bsec.run(bme, on_result, state_path=STATE)
    except KeyboardInterrupt:
        bsec.save_state(STATE)
    finally:
        bme.close()


if __name__ == "__main__":
    main()
