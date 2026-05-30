"""
Binary data logger for BME680 air-quality readings.

Record layout - 10 bytes, little-endian timestamp:

    Bytes 0-3   uint32 LE   Unix timestamp (seconds)
    Bytes 4-9   43-bit packed bitfield (big-endian, 5 spare bits):
                [temp*10 : 11 signed][hum*10 : 10][iaq : 9][co2÷2 : 13]

    Field       Bits    Stored as           Range               Resolution
    ─────────   ────    ─────────           ─────               ──────────
    Timestamp   32      uint32              until 2106          1 s
    Temperature 11      int11 (*10)         -102.4 … +102.3 °C  0.1 °C
    Humidity    10      uint10 (*10)        0 - 102.3 %          0.1 %
    IAQ          9      uint9               0 - 511             1
    CO₂         13      uint13 (÷2)         0 - 16 382 ppm      2 ppm

No file header.  No sync records.  Every record is self-contained.
Append-only.  Thread-safe writes via a lock.
"""

from __future__ import annotations

import struct
import threading
import time
from pathlib import Path

RECORD = 10


class DataLogger:
    def __init__(self, path: str | Path, interval: int = 30) -> None:
        self.path = Path(path)
        self.interval = interval
        self._lock = threading.Lock()
        last_record = self.read_last()
        self._last_log: float = last_record["ts"] if last_record else 0.0
        if not self.path.exists():
            self.path.touch()

    @staticmethod
    def pack(ts: int, temp: float, hum: float, iaq: float, co2: float) -> bytes:
        t = max(-1024, min(1023, round(temp * 10)))
        if t < 0:
            t = t & 0x7FF
        h = max(0, min(1023, round(hum * 10)))
        i = max(0, min(511, round(iaq)))
        c = max(0, min(8191, round(co2 / 2)))

        bits = (t << 32) | (h << 22) | (i << 13) | c
        b5 = (bits >> 40) & 0xFF
        b4 = (bits >> 32) & 0xFF
        b3 = (bits >> 24) & 0xFF
        b2 = (bits >> 16) & 0xFF
        b1 = (bits >> 8) & 0xFF
        b0 = bits & 0xFF

        return struct.pack("<I", ts) + bytes([b5, b4, b3, b2, b1, b0])

    @staticmethod
    def unpack(buf: bytes) -> dict:
        ts = struct.unpack("<I", buf[0:4])[0]
        bits = ((buf[4] << 40) | (buf[5] << 32) | (buf[6] << 24)
                | (buf[7] << 16) | (buf[8] << 8) | buf[9])

        t_raw = (bits >> 32) & 0x7FF
        # sign-extend 11-bit
        if t_raw & 0x400:
            t_raw -= 0x800
        temp = t_raw / 10.0

        hum = ((bits >> 22) & 0x3FF) / 10.0
        iaq = (bits >> 13) & 0x1FF
        co2 = (bits & 0x1FFF) * 2

        return {"ts": ts, "t": temp, "h": hum, "i": iaq, "c": co2}


    def maybe_log(self, temp: float, hum: float, iaq: float, co2: float) -> bool:
        now = time.time()
        if now - self._last_log < self.interval:
            return False
        with self._lock:
            if now - self._last_log < self.interval:
                return False
            record = self.pack(int(now), temp, hum, iaq, co2)
            with Path(self.path).open("ab") as f:
                f.write(record)
            self._last_log = now
            return True


    def read_last(self) -> dict | None:
        try:
            size = self.path.stat().st_size
        except OSError:
            return None
        if size < RECORD:
            return None
        with Path(self.path).open("rb") as f:
            f.seek(size - RECORD)
            return self.unpack(f.read(RECORD))

    def read_tail(self, seconds: int) -> list[dict]:
        try:
            size = self.path.stat().st_size
        except OSError:
            return []
        if size < RECORD:
            return []

        need = int((seconds / max(self.interval, 1)) * RECORD) + RECORD * 20
        offset = max(0, size - need)

        offset -= offset % RECORD

        with Path(self.path).open("rb") as f:
            f.seek(offset)
            raw = f.read()

        cutoff = int(time.time()) - seconds
        records: list[dict] = []
        pos = 0
        while pos + RECORD <= len(raw):
            rec = self.unpack(raw[pos : pos + RECORD])
            pos += RECORD
            if rec["ts"] >= cutoff:
                records.append(rec)
        return records

    def read_all(self) -> list[dict]:
        raw = self.path.read_bytes()
        records: list[dict] = []
        pos = 0
        while pos + RECORD <= len(raw):
            records.append(self.unpack(raw[pos : pos + RECORD]))
            pos += RECORD
        return records


    @staticmethod
    def aggregate(records: list[dict], buckets: int) -> list[dict]:
        if not records:
            return []
        n = len(records)
        if n <= buckets:
            return records
        size = n / buckets
        out: list[dict] = []
        for b in range(buckets):
            lo = int(b * size)
            hi = int((b + 1) * size)
            sl = records[lo:hi]
            if not sl:
                continue
            k = len(sl)
            out.append({
                "ts": sl[k // 2]["ts"],
                "t": round(sum(r["t"] for r in sl) / k, 1),
                "h": round(sum(r["h"] for r in sl) / k, 1),
                "i": round(sum(r["i"] for r in sl) / k),
                "c": round(sum(r["c"] for r in sl) / k),
            })
        return out

    def query(self, range_key: str) -> dict:
        spans = {"day": 86400, "week": 604800, "month": 2592000, "year": 31536000}
        targets = {"day": 360, "week": 336, "month": 360, "year": 365}
        span = spans.get(range_key, 86400)

        if range_key == "year":
            recs = [r for r in self.read_all()
                    if r["ts"] >= int(time.time()) - span]
        else:
            recs = self.read_tail(span)

        pts = self.aggregate(recs, targets.get(range_key, 360))

        stats: dict = {}
        if recs:
            for key in ("t", "h", "i", "c"):
                vals = [r[key] for r in recs]
                stats[key] = {
                    "min": round(min(vals), 1),
                    "max": round(max(vals), 1),
                    "avg": round(sum(vals) / len(vals), 1),
                }

        return {
            "range": range_key,
            "count": len(recs),
            "points": pts,
            "stats": stats,
        }
