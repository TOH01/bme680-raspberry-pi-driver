import ctypes
import os
import time


class _BsecResult(ctypes.Structure):
    _fields_ = [
        ("n_outputs",             ctypes.c_int),
        ("status",                ctypes.c_int),
        ("iaq",                   ctypes.c_float),
        ("static_iaq",            ctypes.c_float),
        ("co2_equivalent",        ctypes.c_float),
        ("breath_voc_equivalent", ctypes.c_float),
        ("temperature",           ctypes.c_float),
        ("humidity",              ctypes.c_float),
        ("stabStatus",            ctypes.c_float),
        ("runInStatus",           ctypes.c_float),
        ("gas_percentage",        ctypes.c_float),
        ("compensated_gas",       ctypes.c_float),
        ("iaq_accuracy",          ctypes.c_ubyte),
    ]


class BsecIAQ:
    def __init__(self, lib_path: str = "./libbsec_wrapper.so"):
        if not os.path.exists(lib_path):
            raise FileNotFoundError(f"BSEC library not found: {lib_path}")
        self._lib = ctypes.CDLL(lib_path)
        self._lib.bsec_compute.restype = _BsecResult
        self._lib.bsec_compute.argtypes = [
            ctypes.c_int64,
            ctypes.c_float,
            ctypes.c_float,
            ctypes.c_float,
            ctypes.c_float,
        ]
        self._lib.bridge_get_state.restype = ctypes.c_int
        self._lib.bridge_get_state.argtypes = [
            ctypes.POINTER(ctypes.c_uint8),
            ctypes.POINTER(ctypes.c_uint32),
        ]
        self._lib.bridge_set_state.restype = ctypes.c_int
        self._lib.bridge_set_state.argtypes = [
            ctypes.POINTER(ctypes.c_uint8),
            ctypes.c_uint32,
        ]
        self._lib.bridge_max_state_size.restype = ctypes.c_uint32
        self._lib.bridge_max_state_size.argtypes = []
        self._state_size = self._lib.bridge_max_state_size()

    def start_bsec(self) -> None:
        status = self._lib.init_bridge()
        if status < 0:
            raise RuntimeError(f"init_bridge failed with status {status}")

    def compute(self, temperature: float, humidity: float, pressure: float,
                gas_resistance: float) -> dict:

        result = self._lib.bsec_compute(
            time.monotonic_ns(),
            ctypes.c_float(temperature),
            ctypes.c_float(humidity),
            ctypes.c_float(pressure),
            ctypes.c_float(gas_resistance),
        )

        if result.status < 0:
            raise RuntimeError(f"bsec_compute failed with status "
                               f"{result.status}")

        if result.n_outputs == 0:
            return None

        return {
            "iaq":                   result.iaq,
            "static_iaq":            result.static_iaq,
            "co2_equivalent":        result.co2_equivalent,
            "breath_voc_equivalent": result.breath_voc_equivalent,
            "temperature":           result.temperature,
            "humidity":              result.humidity,
            "stabStatus":            result.stabStatus,
            "runInStatus":           result.runInStatus,
            "gas_percentage":        result.gas_percentage,
            "compensated_gas":       result.compensated_gas,
            "iaq_accuracy":          result.iaq_accuracy,
        }

    def save_state(self, path: str) -> None:
        buf = (ctypes.c_uint8 * self._state_size)()
        length = ctypes.c_uint32(0)
        status = self._lib.bridge_get_state(buf, ctypes.byref(length))
        if status < 0:
            raise RuntimeError(f"bridge_get_state failed with status {status}")
        with open(path, "wb") as f:
            f.write(bytes(buf[:length.value]))

    def load_state(self, path: str) -> None:
        if not os.path.exists(path):
            return
        with open(path, "rb") as f:
            data = f.read()
        buf = (ctypes.c_uint8 * len(data))(*data)
        status = self._lib.bridge_set_state(buf, ctypes.c_uint32(len(data)))
        if status < 0:
            raise RuntimeError(f"bridge_set_state failed with status {status}")
