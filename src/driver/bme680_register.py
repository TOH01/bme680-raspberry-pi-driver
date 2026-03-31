from .register import Register
from .register_group import RegisterGroup

CHIP_ID_REG       = Register(0xD0)
CTRL_MEAS_REG     = Register(0x74, mask=[0x03])
NEW_DATA_REG      = Register(0x1D, mask=[0x80], shift=7, signed=False)
PAR_T1_REG        = Register(0xE9, size=2, signed=False)
NB_CONV_REG       = Register(0x71, signed=False, mask=[0x0F])
RUN_GAS_REG       = Register(0x71, signed=False, mask=[0x10], shift=4)
GAS_VALID_REG     = Register(0x2B, mask=[0x20], shift=5, signed=False)
HEAT_STAB_REG     = Register(0x2B, mask=[0x10], shift=4, signed=False)
OSRS_H_REG        = Register(0x72, mask=[0x07], signed=False)
OSRS_T_REG        = Register(0x74, mask=[0xE0], shift=5, signed=False)
OSRS_P_REG        = Register(0x74, mask=[0x1C], shift=2, signed=False)
RESET_REG         = Register(0xE0, signed=False)
CONFIG_FILTER_REG = Register(0x75, mask=[0x1C], shift=2, signed=False)

# https://github.com/boschsensortec/BME68x_SensorAPI/blob/80ea120a8b8ac987d7d79eb68a9ed796736be845/bme68x_defs.h#L813
PRESSURE_CAL_REG_GROUP = RegisterGroup({
    "par_p1"  : Register(0x8E, size=2, signed=False),
    "par_p2"  : Register(0x90, size=2),
    "par_p3"  : Register(0x92),
    "par_p4"  : Register(0x94, size=2),
    "par_p5"  : Register(0x96, size=2),
    "par_p6"  : Register(0x99),
    "par_p7"  : Register(0x98),
    "par_p8"  : Register(0x9C, size=2),
    "par_p9"  : Register(0x9E, size=2),
    "par_p10" : Register(0xA0, signed=False),
})

# https://github.com/boschsensortec/BME68x_SensorAPI/blob/80ea120a8b8ac987d7d79eb68a9ed796736be845/bme68x_defs.h#L804
TEMP_CAL_REG_GROUP = RegisterGroup({
    "par_t2": Register(0x8A, size=2),
    "par_t3": Register(0x8C),
})

# https://github.com/boschsensortec/BME68x_SensorAPI/blob/80ea120a8b8ac987d7d79eb68a9ed796736be845/bme68x_defs.h#L774
HUM_CAL_REG_GROUP = RegisterGroup({
    "par_h3": Register(0xE4),
    "par_h4": Register(0xE5),
    "par_h5": Register(0xE6),
    "par_h6": Register(0xE7, signed=False),
    "par_h7": Register(0xE8),
})

# https://github.com/boschsensortec/BME68x_SensorAPI/blob/80ea120a8b8ac987d7d79eb68a9ed796736be845/bme68x_defs.h#L795
GAS_CAL_REG_GROUP = RegisterGroup({
    "par_g1": Register(0xED),
    "par_g2": Register(0xEB, size=2),
    "par_g3": Register(0xEE),
})

# https://github.com/boschsensortec/BME68x_SensorAPI/blob/80ea120a8b8ac987d7d79eb68a9ed796736be845/bme68x_defs.h#L852
RES_HEAT_REG_GROUP = RegisterGroup({
    "res_heat_range"        : Register(0x02, signed=False, mask=[0x30], shift=4),
    "res_heat_val"          : Register(0x00),
    "range_switching_error" : Register(0x04, mask=[0xF0], shift=4),
})

ADC_REG_GROUP = RegisterGroup({
    "gas_adc"   : Register(0x2A, size=2, endianness="big",
                           signed=False, mask=[0xFF, 0xC0], shift=6),
    "gas_range" : Register(0x2B, signed=False, mask=[0x0F]),
    "temp_adc"  : Register(0x22, size=3, endianness="big", signed=False, shift=4),
    "press_adc" : Register(0x1F, size=3, endianness="big", signed=False, shift=4),
    "hum_adc"   : Register(0x25, size=2, endianness="big", signed=False),
})
