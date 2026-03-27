from . import bme680_constants
from . import bme680_register
from .i2c import I2CDevice
from .bme680_compensation import BME680Compensation
import time
from .register import Register


class BME680():
    def __init__(self, bus=1):
        self._bus = bus
        self._connect()
        self.compensation = BME680Compensation.from_device(self.i2c_dev)

    def __enter__(self) -> "BME680":
        return self

    def __exit__(self, *args) -> None:
        self.close()

    def _check_chip_id(self) -> bool:
        chip_id = self.i2c_dev.read_register(bme680_register.CHIP_ID_REG)
        return chip_id == bme680_constants.CHIP_ID

    def _connect(self) -> None:
        for addr in bme680_constants.ADDR_LOOKUP_TABLE:
            self.i2c_dev = I2CDevice.probe(addr, bus=self._bus)
            if self.i2c_dev is None:
                continue
            if self._check_chip_id():
                return
        raise RuntimeError(f"No BME680 found on bus {self._bus}")

    def _verify_heater_profile(self, profile_id: int, time_ms: int,
                               time_multiplier: int) -> None:

        if not 0 <= profile_id < bme680_constants.MAX_HEATER_PROFILES:
            raise ValueError(f"Heater profile {profile_id} not within"
                             f" 0-{bme680_constants.MAX_HEATER_PROFILES}")
        if not 0 <= time_ms <= bme680_constants.MAX_HEATER_WAIT_VALUE:
            raise ValueError(f"Heater base wait {time_ms} not within"
                             f" 0-{bme680_constants.MAX_HEATER_WAIT_VALUE}")
        if time_multiplier not in bme680_constants.HEATER_WAIT_MULTIPLIERS:
            raise ValueError(f"Heater wait multiplier {time_multiplier} not in"
                             f" {bme680_constants.HEATER_WAIT_MULTIPLIERS}")

    def _encode_gas_wait_x(self, time_ms: int, time_multiplier: int) -> int:
        return time_multiplier << 6 | (time_ms & 0x3F)

    def close(self) -> None:
        self.i2c_dev.bus.close()

    def set_forced_mode(self) -> None:
        self.i2c_dev.write_register_masked(bme680_register.CTRL_MEAS_REG, 0x01)

    def get_compensated_tph(self) -> dict[str, float]:
        regs = self.i2c_dev.read_register_group(bme680_register.ADC_REG_GROUP)
        temp_adc = regs["temp_adc"]
        press_adc = regs["press_adc"]
        hum_adc = regs["hum_adc"]

        t_fine = self.compensation.calc_t_fine(temp_adc)
        t_comp = self.compensation.t_fine_to_temp_comp(t_fine)
        p_comp = self.compensation.calc_press_comp(press_adc, t_fine)
        h_comp = self.compensation.calc_hum_comp(hum_adc, t_comp)

        return {
            "temperature": t_comp,
            "pressure": p_comp,
            "humidity": h_comp
        }

    def wait_for_tph_measurement(self, timeout_ms: int = 500) -> bool:
        deadline = time.monotonic() + timeout_ms / 1000
        while time.monotonic() < deadline:
            if self.i2c_dev.read_register(bme680_register.NEW_DATA_REG):
                return True
            time.sleep(0.01)
        return False

    def get_res_heat_val(self, ambient_temp: int, target_temp: int) -> int:
        return self.compensation.calc_gas_res_heat_val(ambient_temp,
                                                       target_temp)

    def configure_heater_profile(self, profile_id: int, time_ms: int,
                                 time_multiplier: int,
                                 res_heat_val: int) -> None:

        self._verify_heater_profile(profile_id, time_ms, time_multiplier)
        gas_wait_x_val = bme680_constants.GAS_WAIT_X_START_ADDR + profile_id
        gas_wait_x_reg = Register(gas_wait_x_val, signed=False)
        res_heat_x_val = bme680_constants.RES_HEAT_X_START_ADDR + profile_id
        res_heat_x_reg = Register(res_heat_x_val, signed=False)

        self.i2c_dev.write_register(gas_wait_x_reg,
                                    self._encode_gas_wait_x(time_ms,
                                                            time_multiplier))

        self.i2c_dev.write_register(res_heat_x_reg, res_heat_val)

    def activate_heater_profile(self, profile_id: int) -> None:
        self.i2c_dev.write_register_masked(bme680_register.NB_CONV_REG,
                                           profile_id)

    def activate_gas_conversion(self) -> None:
        self.i2c_dev.write_register_masked(bme680_register.RUN_GAS_REG, 0x1)

    def wait_for_gas_measurement(self, timeout_ms: int = 500) -> bool:
        deadline = time.monotonic() + timeout_ms / 1000
        while time.monotonic() < deadline:
            heat_stable = self.i2c_dev.read_register(
                bme680_register.HEAT_STAB_REG)
            gas_valid = self.i2c_dev.read_register(
                bme680_register.GAS_VALID_REG)
            if heat_stable and gas_valid:
                return True
            time.sleep(0.01)
        return False

    def get_gas_res(self) -> dict[str, float]:
        regs = self.i2c_dev.read_register_group(bme680_register.ADC_REG_GROUP)
        gas_adc = regs["gas_adc"]
        gas_range = regs["gas_range"]
        gas_res = self.compensation.calc_gas_res(gas_adc, gas_range)

        return {
            "gas_res": gas_res
        }
