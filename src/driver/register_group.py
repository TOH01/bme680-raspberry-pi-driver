from .register import Register


class RegisterGroup():
    def __init__(self, regs: dict[str, Register]):
        self.regs = regs
        self.start, self.n_bytes = self.get_range()

    def get_range(self) -> tuple[int, int]:
        start, end = 0xFF, 0x00
        for reg in self.regs.values():
            if reg.start < start:
                start = reg.start
            if reg.start + reg.size > end:
                end = reg.start + reg.size
        return start, end - start
