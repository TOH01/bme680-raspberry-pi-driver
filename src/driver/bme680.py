from . import bme680_constants
from . import bme680_register
from .i2c import I2CDevice
from .bme680_compensation import BME680Compensation


class BME680():
    def __init__(self, bus=1):
        self._bus = bus
        self._connect()
        self.compensation = BME680Compensation.from_device(self.i2c_dev)

    def _check_chip_id(self) -> bool:
        chip_id = self.i2c_dev.read_register(bme680_register.CHIP_ID_REG)
        return chip_id == bme680_constants.CHIP_ID

    def _connect(self):
        for addr in bme680_constants.ADDR_LOOKUP_TABLE:
            self.i2c_dev = I2CDevice.probe(addr, bus=self._bus)
            if self.i2c_dev is None:
                continue
            if self._check_chip_id():
                return
        raise RuntimeError(f"No BME680 found on bus {self._bus}")

    def set_forced_mode(self):
        self.i2c_dev.write_register_masked(bme680_register.CTRL_MEAS_REG, 0x01)

    def get_compensated_tph(self) -> dict[str, int]:
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
