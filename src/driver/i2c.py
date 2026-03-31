from types import TracebackType

from smbus2 import SMBus

from .register import Register
from .register_group import RegisterGroup


class I2CDevice:
    def __init__(self, address: int, bus: int = 1) -> None:
        self.bus = SMBus(bus)
        self.address = address
        self._verify_address()

    def _verify_address(self) -> None:
        try:
            self.bus.read_byte(self.address)
        except OSError:
            raise RuntimeError(f"No I2C device at {self.address:#04x}") from None

    @classmethod
    def probe(cls, address: int, bus: int = 1) -> "I2CDevice | None":
        try:
            return cls(address, bus)
        except RuntimeError:
            return None

    def __enter__(self) -> "I2CDevice":
        return self

    def __exit__(self, typ: type[BaseException] | None, exc: BaseException | None,
                 tb: TracebackType | None) -> None:

        self.bus.close()

    def read_byte_at(self, reg: int) -> int:
        return self.bus.read_byte_data(self.address, reg)

    def read_at(self, reg: int, size: int) -> list[int]:
        return self.bus.read_i2c_block_data(self.address, reg, size)

    def write_at(self, reg: int, data: list[int]) -> None:
        self.bus.write_i2c_block_data(self.address, reg, data)

    def read_register(self, register: Register) -> int:
        raw_register = self.read_at(register.start, register.size)
        return register.from_raw(raw_register)

    def write_register(self, register: Register, value: int) -> None:
        self.write_at(register.start, register.to_raw(value))

    def write_register_masked(self, register: Register, value: int) -> None:
        if not register.mask:
            raise ValueError("Register has no mask defined")

        current = self.read_at(register.start, register.size)
        raw = register.to_raw(value)
        merged = [
            (c & ~m) | (r & m)
            for c, r, m in zip(current, raw, register.mask, strict=True)
        ]
        self.write_at(register.start, merged)

    def read_register_group(self, register_group: RegisterGroup) -> dict[str, int]:
        start, size = register_group.start, register_group.size
        raw = self.read_at(start, size)
        regs = {}

        for reg_name, reg in register_group.regs.items():
            offset = reg.start - register_group.start
            raw_chunk = raw[offset: offset + reg.size]
            regs[reg_name] = reg.from_raw(raw_chunk)

        return regs
