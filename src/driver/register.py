class Register():
    def __init__(self, start: int, size: int = 1, endianness: str = "little",
                 signed: bool = True, shift: int = 0,
                 mask: list[int] | None = None):

        self.start = start
        self.size = size
        self.endianness = endianness
        self.signed = signed
        self.shift = shift
        self.mask = mask

    def from_raw(self, raw: list[int]) -> int:
        reg = []
        if self.mask:
            for idx, byte_mask in enumerate(self.mask):
                reg.append(raw[idx] & byte_mask)
        else:
            reg = raw
        return int.from_bytes(reg, byteorder=self.endianness,
                              signed=self.signed) >> self.shift

    def to_raw(self, value: int) -> list[int]:
        value = value << self.shift
        raw = list(value.to_bytes(self.size, byteorder=self.endianness,
                                  signed=self.signed))
        if self.mask:
            for idx, byte_mask in enumerate(self.mask):
                raw[idx] = raw[idx] & byte_mask
        return raw
