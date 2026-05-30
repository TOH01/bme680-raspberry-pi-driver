import argparse
import json
import time
from pathlib import Path

from flask import Flask, Response, request

from examples.m5_stack.datalogger import DataLogger

_DIR = Path(__file__).parent
LOG = _DIR / "airquality.bin"
LATEST = _DIR / "latest.json"

app = Flask(__name__)
_logger: DataLogger | None = None
_html: str = ""


def _read_latest() -> dict | None:
    """Read the latest sensor reading written by sensor.py."""
    try:
        return json.loads(LATEST.read_text())
    except (OSError, json.JSONDecodeError):
        return None


@app.route("/")
@app.route("/history")
def index():
    return _html


@app.route("/events")
def events():
    """SSE stream.  Reads latest.json every 3 s.  Adds _stale flag
    so the dashboard can show a warning if the sensor is down."""
    def gen():
        last_sent = None
        while True:
            d = _read_latest()
            if d is not None:
                ts = d.get("timestamp", 0)
                stale = (time.time() - ts) > 90
                d["_stale"] = stale
                payload = json.dumps(d)
                if payload != last_sent:
                    yield f"data: {payload}\n\n"
                    last_sent = payload
            time.sleep(3)
    return Response(
        gen(),
        content_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.route("/history/data")
def history_data():
    r = request.args.get("range", "day")
    if r not in ("day", "week", "month", "year"):
        r = "day"
    return Response(
        json.dumps(_logger.query(r)),
        content_type="application/json",
    )


_TEMPLATE = (_DIR / "index.html").read_text(encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="BME680 air-quality web server")
    parser.add_argument(
        "--room", "-r",
        default="Living room",
        help="Room name shown in the dashboard (default: Living room)",
    )
    parser.add_argument(
        "--port", "-p",
        type=int, default=8080,
        help="HTTP port (default: 8080)",
    )
    args = parser.parse_args()

    _html = _TEMPLATE.replace("__ROOM__", json.dumps(args.room))
    _logger = DataLogger(LOG)

    print(f"[web] serving on https://0.0.0.0:{args.port}")
    app.run(
        host="0.0.0.0",
        port=args.port,
        threaded=True,
        ssl_context="adhoc",
    )
