from typing import Tuple, Union, Callable

HORIZONTAL = 0
VERTICAL = 1
FULL_LENGTH = -1
FULL_WIDTH = -1
FULL_HEIGHT = -1
FULL_SIZE = (FULL_WIDTH, FULL_HEIGHT)
GROW_LENGTH = None
GROW_WIDTH = None
GROW_HEIGHT = None
GROW_SIZE = (None, None)

Resize = Tuple[bool, bool]
Position = Tuple[int, int]
Orientation = Union[int, int]
CLISizeObserver = Callable[[Resize], None]