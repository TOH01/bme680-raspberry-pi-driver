import ctypes
import logging
import time
from collections.abc import Callable
from pathlib import Path
from typing import TypedDict

from driver import BME680
from driver.bme680 import TPHResult

from . import bsec_constants

logger = logging.getLogger(__name__)

def check_return(status : int, fn_name : str) -> None:
    return_formatted = f"{bsec_constants.RETURN_CODES[status]} ({status})"
    if status < bsec_constants.OK:
        raise RuntimeError(f"bsec_wrapper.c - {fn_name} failed with {return_formatted}")
    if status !=  bsec_constants.OK:
        logger.warning(f"bsec_wrapper.c - {fn_name} returned {return_formatted}")

class BsecResult(TypedDict):
    iaq: float
    static_iaq: float
    co2_equivalent: float
    breath_voc_equivalent: float
    temperature: float
    humidity: float
    stab_status: float
    run_in_status: float
    gas_percentage: float
    compensated_gas: float
    iaq_accuracy: int
    timestamp: int


class BsecSettings(TypedDict):
    next_call_ns: int
    heater_temperature: int
    heater_duration: int
    run_gas: bool
    temperature_oversampling: int
    pressure_oversampling: int
    humidity_oversampling: int
    trigger_measurement: bool
    process_data: int


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
        ("stab_status",           ctypes.c_float),
        ("run_in_status",         ctypes.c_float),
        ("gas_percentage",        ctypes.c_float),
        ("compensated_gas",       ctypes.c_float),
        ("iaq_accuracy",          ctypes.c_ubyte),
    ]


class _BsecSettings(ctypes.Structure):
    _fields_ = [
        ("status",                   ctypes.c_int),
        ("next_call_ns",             ctypes.c_int64),
        ("heater_temperature",       ctypes.c_uint16),
        ("heater_duration",          ctypes.c_uint16),
        ("run_gas",                  ctypes.c_ubyte),
        ("temperature_oversampling", ctypes.c_ubyte),
        ("pressure_oversampling",    ctypes.c_ubyte),
        ("humidity_oversampling",    ctypes.c_ubyte),
        ("trigger_measurement",      ctypes.c_ubyte),
        ("process_data",             ctypes.c_uint32),
    ]


class BsecIAQ:
    def __init__(self, lib_path: str = "./libbsec_wrapper.so") -> None:
        if not Path(lib_path).exists():
            raise FileNotFoundError(f"BSEC library not found: {lib_path}")

        # bsec_result_t bsec_compute();
        self._lib = ctypes.CDLL(lib_path)
        self._lib.bsec_compute.restype = _BsecResult
        self._lib.bsec_compute.argtypes = [
            ctypes.c_int64,   # int64_t  timestamp_ns
            ctypes.c_float,   # float    temperature
            ctypes.c_float,   # float    humidity
            ctypes.c_float,   # float    pressure
            ctypes.c_float,   # float    gas_resistance
            ctypes.c_uint32,  # uint32_t process_data
        ]

        # int bridge_get_state();
        self._lib.bridge_get_state.restype = ctypes.c_int
        self._lib.bridge_get_state.argtypes = [
            ctypes.POINTER(ctypes.c_uint8),   # uint8_t  *state_buffer
            ctypes.POINTER(ctypes.c_uint32),  # uint32_t *state_len
        ]

        # int bridge_set_state();
        self._lib.bridge_set_state.restype = ctypes.c_int
        self._lib.bridge_set_state.argtypes = [
            ctypes.POINTER(ctypes.c_uint8),  # uint8_t  *state_buffer
            ctypes.c_uint32,                 # uint32_t state_len
        ]

        # uint32_t bridge_max_state_size(void);
        self._lib.bridge_max_state_size.restype = ctypes.c_uint32
        self._lib.bridge_max_state_size.argtypes = []
        self._state_size = self._lib.bridge_max_state_size()

        # bsec_settings_t bridge_sensor_control();
        self._lib.bridge_sensor_control.restype = _BsecSettings
        self._lib.bridge_sensor_control.argtypes = [
            ctypes.c_int64,  # int64_t timestamp_ns
        ]

    def _apply_bsec_settings(self, bme680: BME680, settings: dict,
                             ambient_temp: int) -> None:

        if settings["temperature_oversampling"] > 0:
            bme680.set_temperature_oversampling(settings["temperature_oversampling"])
        if settings["pressure_oversampling"] > 0:
            bme680.set_pressure_oversampling(settings["pressure_oversampling"])
        if settings["humidity_oversampling"] > 0:
            bme680.set_humidity_oversampling(settings["humidity_oversampling"])

        if settings["run_gas"]:
            base_ms, multiplier = bme680.calc_gas_wait_params(
                settings["heater_duration"],
            )
            res_heat = bme680.get_res_heat_val(ambient_temp,
                                               settings["heater_temperature"])

            bme680.configure_heater_profile(0, base_ms, multiplier, res_heat)
            bme680.activate_heater_profile(0)
            bme680.activate_gas_conversion()

    def start_bsec(self) -> None:
        status = self._lib.init_bridge()
        check_return(status, "init_bridge()")

    def compute(self, timestamp_ns: int, tph_result: TPHResult, gas_resistance: float,
                process_data: int) -> BsecResult | None:

        result = self._lib.bsec_compute(
            timestamp_ns,
            ctypes.c_float(tph_result["temperature"]),
            ctypes.c_float(tph_result["humidity"]),
            ctypes.c_float(tph_result["pressure"]),
            ctypes.c_float(gas_resistance),
            ctypes.c_uint32(process_data),
        )

        check_return(result.status, "bsec_compute()")

        if result.n_outputs == 0:
            logger.warning("bsec_compute() result with n_outpus=0")
            return None

        return {
            "iaq":                   result.iaq,
            "static_iaq":            result.static_iaq,
            "co2_equivalent":        result.co2_equivalent,
            "breath_voc_equivalent": result.breath_voc_equivalent,
            "temperature":           result.temperature,
            "humidity":              result.humidity,
            "stab_status":           result.stab_status,
            "run_in_status":         result.run_in_status,
            "gas_percentage":        result.gas_percentage,
            "compensated_gas":       result.compensated_gas,
            "iaq_accuracy":          result.iaq_accuracy,
            "timestamp":             timestamp_ns,
        }

    def save_state(self, path: str) -> None:
        buf = (ctypes.c_uint8 * self._state_size)()
        length = ctypes.c_uint32(0)

        status = self._lib.bridge_get_state(buf, ctypes.byref(length))
        check_return(status, "bridge_get_state()")

        data = bytes(buf[:length.value])

        tmp = Path(path).with_suffix(".tmp")
        with tmp.open("wb") as f:
            f.write(data)

        tmp.replace(path)

    def load_state(self, path: str) -> None:
        if not Path(path).exists():
            return
        with Path(path).open("rb") as f:
            data = f.read()
        buf = (ctypes.c_uint8 * len(data))(*data)

        status = self._lib.bridge_set_state(buf, ctypes.c_uint32(len(data)))
        check_return(status, "bridge_set_state()")

    def get_sensor_settings(self, timestamp_ns: int) -> BsecSettings:
        settings = self._lib.bridge_sensor_control(timestamp_ns)
        check_return(settings.status, "bridge_sensor_control()")

        return {
            "next_call_ns":             settings.next_call_ns,
            "heater_temperature":       settings.heater_temperature,
            "heater_duration":          settings.heater_duration,
            "run_gas":                  bool(settings.run_gas),
            "temperature_oversampling": settings.temperature_oversampling,
            "pressure_oversampling":    settings.pressure_oversampling,
            "humidity_oversampling":    settings.humidity_oversampling,
            "trigger_measurement":      bool(settings.trigger_measurement),
            "process_data":             settings.process_data,
        }

    def run(self, bme680: BME680, callback: Callable[[BsecResult], None],
            state_path: str | None = None, initial_amb_temp: int = 25) -> None:

        self.start_bsec()

        if state_path:
            self.load_state(state_path)

        last_temp = initial_amb_temp
        last_save = time.monotonic_ns()

        while True:
            timestamp_ns = time.monotonic_ns()
            settings = self.get_sensor_settings(timestamp_ns)

            if not settings["trigger_measurement"]:
                time.sleep(0.1)
                continue

            self._apply_bsec_settings(bme680, settings, last_temp)
            bme680.set_forced_mode()

            if not bme680.wait_for_tph_measurement():
                logger.warning("TPH measurement timeout")
                continue

            tph = bme680.get_compensated_tph()

            gas_res = 0.0

            if settings["run_gas"]:
                if not bme680.wait_for_gas_measurement():
                    logger.warning("gas measurement timeout")
                    continue
                gas_res = bme680.get_gas_res()

            result = self.compute(timestamp_ns, tph, gas_res, settings["process_data"])

            if result is not None:
                last_temp = int(tph["temperature"])
                callback(result)

            time_since_save = timestamp_ns - last_save
            if state_path and time_since_save >= bsec_constants.STATE_SAVE_INTERVAL:
                self.save_state(state_path)
                last_save = timestamp_ns

            wait_ns = settings["next_call_ns"] - timestamp_ns
            if wait_ns > 0:
                time.sleep(wait_ns / 1_000_000_000)
