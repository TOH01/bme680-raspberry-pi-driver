from .register import Register


class RegisterGroup:
    def __init__(self, regs: dict[str, Register]) -> None:
        self.regs = regs
        self.start, self.size = self._get_range()

    def _get_range(self) -> tuple[int, int]:
        start, end = 0xFF, 0x00
        for reg in self.regs.values():
            start = min(start, reg.start)
            end = max(end, reg.start + reg.size)
        return start, end - start
