from .i2c import I2CDevice
from .register_group import RegisterGroup
from . import bme680_register
from . import bme680_constants


class BME680Compensation:
    def __init__(self):
        # Temperature
        self.par_t1: int = 0
        self.par_t2: int = 0
        self.par_t3: int = 0
        # Pressure
        self.par_p1:  int = 0
        self.par_p2:  int = 0
        self.par_p3:  int = 0
        self.par_p4:  int = 0
        self.par_p5:  int = 0
        self.par_p6:  int = 0
        self.par_p7:  int = 0
        self.par_p8:  int = 0
        self.par_p9:  int = 0
        self.par_p10: int = 0
        # Humidity
        self.par_h1: int = 0
        self.par_h2: int = 0
        self.par_h3: int = 0
        self.par_h4: int = 0
        self.par_h5: int = 0
        self.par_h6: int = 0
        self.par_h7: int = 0
        # Gas
        self.par_g1: int = 0
        self.par_g2: int = 0
        self.par_g3: int = 0
        # Res heat
        self.res_heat_range: int = 0
        self.res_heat_val:  int = 0

        self.range_switching_error: int = 0

    @classmethod
    def from_device(cls, i2c_dev: I2CDevice) -> "BME680Compensation":
        cal = cls()
        cal._load_temp(i2c_dev)
        cal._load_pressure(i2c_dev)
        cal._load_humidity(i2c_dev)
        cal._load_gas(i2c_dev)
        cal._load_res_heat(i2c_dev)
        return cal

    def _load_group(self, i2c_dev: I2CDevice, group: RegisterGroup) -> None:
        for key, val in i2c_dev.read_register_group(group).items():
            setattr(self, key, val)

    def _load_temp(self, i2c_dev: I2CDevice) -> None:
        self.par_t1 = i2c_dev.read_register(bme680_register.PAR_T1_REG)
        self._load_group(i2c_dev, bme680_register.TEMP_CAL_REG_GROUP)

    def _load_pressure(self, i2c_dev: I2CDevice) -> None:
        self._load_group(i2c_dev, bme680_register.PRESSURE_CAL_REG_GROUP)

    def _load_humidity(self, i2c_dev: I2CDevice) -> None:
        e1 = i2c_dev.read_byte_at(0xE1)
        e2 = i2c_dev.read_byte_at(0xE2)
        e3 = i2c_dev.read_byte_at(0xE3)
        self.par_h1 = (e3 << 4) | (e2 & 0x0F)
        self.par_h2 = (e1 << 4) | (e2 >> 4)
        self._load_group(i2c_dev, bme680_register.HUM_CAL_REG_GROUP)

    def _load_gas(self, i2c_dev: I2CDevice) -> None:
        self._load_group(i2c_dev, bme680_register.GAS_CAL_REG_GROUP)

    def _load_res_heat(self, i2c_dev: I2CDevice) -> None:
        self._load_group(i2c_dev, bme680_register.RES_HEAT_REG_GROUP)

    # 3.3.1 Temperature measurement
    def calc_t_fine(self, temp_adc: int) -> float:
        var1 = ((temp_adc / 16384.0) - (self.par_t1 / 1024.0)) * self.par_t2
        var2 = (((temp_adc / 131072.0) - (self.par_t1 / 8192.0)) * ((temp_adc / 131072.0) - (self.par_t1 / 8192.0))) * (self.par_t3 * 16.0)  # noqa: E501
        return var1 + var2

    # 3.3.1 Temperature measurement
    def t_fine_to_temp_comp(self, t_fine: float) -> float:
        return t_fine / 5120.0

    # 3.3.2 Pressure measurement
    def calc_press_comp(self, press_adc: int, t_fine: int) -> float:
        var1 = (t_fine / 2.0) - 64000.0
        var2 = var1 * var1 * (self.par_p6 / 131072.0)
        var2 = var2 + (var1 * self.par_p5 * 2.0)
        var2 = (var2 / 4.0) + (self.par_p4 * 65536.0)
        var1 = (((self.par_p3 * var1 * var1) / 16384.0) + (self.par_p2 * var1)) / 524288.0  # noqa: E501
        var1 = (1.0 + (var1 / 32768.0)) * self.par_p1
        press_comp = 1048576.0 - press_adc

        # https://github.com/boschsensortec/BME68x_SensorAPI/blob/80ea120a8b8ac987d7d79eb68a9ed796736be845/bme68x.c#L1056
        if var1 != 0:
            press_comp = ((press_comp - (var2 / 4096.0)) * 6250.0) / var1
            var1 = (self.par_p9 * press_comp * press_comp) / 2147483648.0
            var2 = press_comp * (self.par_p8 / 32768.0)
            var3 = (press_comp / 256.0) ** 3 * self.par_p10 / 131072.0
            press_comp = press_comp + (var1 + var2 + var3 + (self.par_p7 * 128.0)) / 16.0  # noqa: E501
        else:
            press_comp = 0

        return press_comp

    # 3.3.3 Humidity measurement
    def calc_hum_comp(self, hum_adc: int, temp_comp: int) -> float:
        var1 = hum_adc - ((self.par_h1 * 16.0) + ((self.par_h3 / 2.0) * temp_comp))  # noqa: E501
        var2 = var1 * ((self.par_h2 / 262144.0) * (1.0 + ((self.par_h4 / 16384.0) * temp_comp) + ((self.par_h5 / 1048576.0) * temp_comp * temp_comp)))  # noqa: E501
        var3 = self.par_h6 / 16384.0
        var4 = self.par_h7 / 2097152.0
        hum_comp = var2 + ((var3 + (var4 * temp_comp)) * var2 * var2)

        # https://github.com/boschsensortec/BME68x_SensorAPI/blob/80ea120a8b8ac987d7d79eb68a9ed796736be845/bme68x.c#L1093
        if hum_comp > 100.0:
            hum_comp = 100.0
        elif hum_comp < 0.0:
            hum_comp = 0.0

        return hum_comp

    # 3.3.5 Gas sensor heating and measurement
    def calc_gas_res_heat_val(self, amb_temp: int, target_temp: int) -> int:
        var1 = (self.par_g1 / 16.0) + 49.0
        var2 = ((self.par_g2 / 32768.0) * 0.0005) + 0.00235
        var3 = self.par_g3 / 1024.0
        var4 = var1 * (1.0 + (var2 * target_temp))
        var5 = var4 + (var3 * amb_temp)
        res_heat_x = int((3.4 * ((var5 * (4.0 / (4.0 + self.res_heat_range)) * (1.0/(1.0 + (self.res_heat_val * 0.002)))) - 25)))  # noqa: E501
        res_heat_int8 = 0xFF & res_heat_x
        return res_heat_int8

    # 3.4.1 Gas sensor resistance readout
    def calc_gas_res(self, gas_adc: int, gas_range: int) -> float:
        var1 = (1340.0 + 5.0 * self.range_switching_error) * bme680_constants.const_array1[gas_range]  # noqa: E501
        gas_res = var1 * bme680_constants.const_array2[gas_range] / (gas_adc - 512.0 + var1)  # noqa: E501
        return gas_res
