from typing import Optional, Tuple


# Globally unique identifier (just easier to read an integer rather than hex)
_next_ident: int = 0


class SimObject:
    def __init__(self):
        global _next_ident
        self.ident = _next_ident
        _next_ident += 1

    def __hash__(self):
        return self.ident

    def __repr__(self):
        return f'{self.__class__.__name__}({self.ident})'

    def __str__(self):
        return self.__repr__()


class Train(SimObject):
    def __init__(self, length: int):
        super().__init__()
        self.length = length


class Signal(SimObject):
    def __init__(self):
        super().__init__()


class Junction(SimObject):
    def __init__(self):
        super().__init__()
        self.fork_connections: Optional[Tuple[int, int]] = None

    def set_forks(self, fork1: int, fork2: int):
        self.fork_connections = (fork1, fork2)
