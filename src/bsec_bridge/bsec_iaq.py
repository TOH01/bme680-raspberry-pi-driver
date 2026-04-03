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
    _fields_ = [  # noqa: RUF012
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
    _fields_ = [  # noqa: RUF012
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

        self._lib = ctypes.CDLL(lib_path)

        # int BsecBridge_Init(void);
        self._lib.BsecBridge_Init.restype = ctypes.c_int
        self._lib.BsecBridge_Init.argtypes = []

        # int BsecBridge_SetConfiguration(void);
        self._lib.BsecBridge_SetConfiguration.restype = ctypes.c_int
        self._lib.BsecBridge_SetConfiguration.argtypes = []

        # int BsecBridge_UpdateSubscription(void);
        self._lib.BsecBridge_UpdateSubscription.restype = ctypes.c_int
        self._lib.BsecBridge_UpdateSubscription.argtypes = []

        # bsec_settings_t BsecBridge_SensorControl(int64_t timestamp_ns);
        self._lib.BsecBridge_SensorControl.restype = _BsecSettings
        self._lib.BsecBridge_SensorControl.argtypes = [
            ctypes.c_int64,  # int64_t timestamp_ns
        ]

        # bsec_result_t BsecBridge_DoSteps(int64_t timestamp_ns, ...);
        self._lib.BsecBridge_DoSteps.restype = _BsecResult
        self._lib.BsecBridge_DoSteps.argtypes = [
            ctypes.c_int64,   # int64_t  timestamp_ns
            ctypes.c_float,   # float    temperature
            ctypes.c_float,   # float    humidity
            ctypes.c_float,   # float    pressure
            ctypes.c_float,   # float    gas_resistance
            ctypes.c_uint32,  # uint32_t process_data
        ]

        # int BsecBridge_GetState(uint8_t *state_buffer, uint32_t *state_len);
        self._lib.BsecBridge_GetState.restype = ctypes.c_int
        self._lib.BsecBridge_GetState.argtypes = [
            ctypes.POINTER(ctypes.c_uint8),   # uint8_t  *state_buffer
            ctypes.POINTER(ctypes.c_uint32),  # uint32_t *state_len
        ]

        # int BsecBridge_SetState(uint8_t *state_buffer, uint32_t state_len);
        self._lib.BsecBridge_SetState.restype = ctypes.c_int
        self._lib.BsecBridge_SetState.argtypes = [
            ctypes.POINTER(ctypes.c_uint8),  # uint8_t  *state_buffer
            ctypes.c_uint32,                 # uint32_t state_len
        ]

        # uint32_t BsecBridge_GetMaxStateSize(void);
        self._lib.BsecBridge_GetMaxStateSize.restype = ctypes.c_uint32
        self._lib.BsecBridge_GetMaxStateSize.argtypes = []

        self._state_size = self._lib.BsecBridge_GetMaxStateSize()

    def _check_state_size(self, data: bytes) -> None:
        if len(data) > self._state_size:
            raise ValueError(f"State file too large: {len(data)} > {self._state_size}")

    def _check_return(self, status : int, fn_name : str) -> None:
        if status == bsec_constants.OK:
            return

        return_formatted = f"{bsec_constants.RETURN_CODES[status]} ({status})"
        fn_mod_formatted = f"bsec_bridge.c - {fn_name}"

        if status < bsec_constants.OK:
            raise RuntimeError(f"{fn_mod_formatted} failed with {return_formatted}")
        if status !=  bsec_constants.OK:
            logger.warning(f"{fn_mod_formatted} returned {return_formatted}")

    def _check_n_outputs(self, n_outputs: int) -> bool:
        if n_outputs == 0:
            logger.warning("n_outputs is 0")
            return False
        return True

    def _apply_bsec_settings(self, bme680: BME680, settings: BsecSettings,
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
            res_heat = bme680.get_res_heat_val(
                ambient_temp,
                settings["heater_temperature"],
            )

            bme680.configure_heater_profile(0, base_ms, multiplier, res_heat)
            bme680.activate_heater_profile(0)
            bme680.activate_gas_conversion()


    def init_bsec(self, state_path: str | None = None) -> None:
        """
        BST-BME-Integration-Guide, 2.2 Integration of BSEC Interfaces

        Initialization sequence for the BSEC library:
        1. bsec_init()               : Initialization of library
        2. bsec_set_configuration()  : Update configuration settings (optional)
        3. bsec_set_state()          : Restore state of library (optional)
        """

        self._check_return(self._lib.BsecBridge_Init(), "BsecBridge_Init()")

        # configuration compiled into SetConfiguration() by compile.sh
        self._check_return(
            self._lib.BsecBridge_SetConfiguration(),
            "BsecBridge_SetConfiguration",
        )

        if state_path and Path(state_path).exists():
            data = Path(state_path).read_bytes()
            self._check_state_size(data)

            buf = (ctypes.c_uint8 * len(data))(*data)

            self._check_return(
                self._lib.BsecBridge_SetState(buf, ctypes.c_uint32(len(data))),
                "BsecBridge_SetState()",
            )
        else:
            logger.warning("init_bsec called without valid state file path")

    def subscribe_bsec(self) -> None:
        """
        BST-BME-Integration-Guide, 2.2 Integration of BSEC Interfaces

        Subscribe ouputs:
        - Enable library outputs with specified mode
        """

        self._check_return(
            self._lib.BsecBridge_UpdateSubscription(),
            "BsecBridge_UpdateSubscription()",
        )

    def sensor_control(self, timestamp_ns: int) -> BsecSettings:
        """
        BST-BME-Integration-Guide, 2.2 Integration of BSEC Interfaces

        Signal processing with BSEC library:
        - Retrieve BME68x sensor instructions
        """

        settings = self._lib.BsecBridge_SensorControl(timestamp_ns)
        self._check_return(settings.status, "BsecBridge_SensorControl()")

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

    def do_steps(self, timestamp_ns: int, tph_result: TPHResult, gas_resistance: float,
                process_data: int) -> BsecResult | None:
        """
        BST-BME-Integration-Guide, 2.2 Integration of BSEC Interfaces

        Signal processing with BSEC library:
        - Main signal processing function
        """

        result = self._lib.BsecBridge_DoSteps(
            timestamp_ns,
            ctypes.c_float(tph_result["temperature"]),
            ctypes.c_float(tph_result["humidity"]),
            ctypes.c_float(tph_result["pressure"]),
            ctypes.c_float(gas_resistance),
            ctypes.c_uint32(process_data),
        )

        self._check_return(result.status, "BsecBridge_DoSteps()")

        if self._check_n_outputs(result.n_outputs):
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

        return None

    def save_state(self, path: str) -> None:
        buf = (ctypes.c_uint8 * self._state_size)()
        length = ctypes.c_uint32(0)

        self._check_return(
            self._lib.BsecBridge_GetState(buf, ctypes.byref(length)),
            "BsecBridge_GetState()",
        )

        data = bytes(buf[:length.value])

        tmp = Path(path).with_suffix(".tmp")
        with tmp.open("wb") as f:
            f.write(data)

        tmp.replace(path)

    def run(self, bme680: BME680, callback: Callable[[BsecResult], None],
            state_path: str | None = None, initial_amb_temp: int = 25) -> None:

        last_temp = initial_amb_temp
        initial_timestamp_ns = time.monotonic_ns()
        last_save = initial_timestamp_ns

        self.init_bsec(state_path)
        self.subscribe_bsec()

        settings = self.sensor_control(initial_timestamp_ns)

        while True:
            wait_ns = settings["next_call_ns"] - time.monotonic_ns()
            if wait_ns > 0:
                time.sleep(wait_ns / 1_000_000_000)

            timestamp_ns = time.monotonic_ns()
            settings = self.sensor_control(timestamp_ns)

            if not settings["trigger_measurement"]:
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

            result = self.do_steps(timestamp_ns, tph, gas_res, settings["process_data"])

            if result is not None:
                last_temp = int(tph["temperature"])
                callback(result)

            time_since_save = timestamp_ns - last_save
            if state_path and time_since_save >= bsec_constants.STATE_SAVE_INTERVAL_NS:
                self.save_state(state_path)
                last_save = timestamp_ns
