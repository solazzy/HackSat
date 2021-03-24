from enum import Enum

from asciimatics.event import MouseEvent

from rbs_tui_dom.dom.types import Resize, Position


class DOMEventType(Enum):
    RESIZE = "resize"
    MOUSE = "click"
    FOCUS = "focus"
    BLUR = "blur"
    KEYBOARD = "keyboard"


class DOMEvent:
    def __init__(self, event_type: DOMEventType, target: 'DOMElement', current_target: 'DOMElement'=None):
        self.event_type = event_type
        self.target = target
        self.current_target = target if current_target is None else current_target
        self.stop_propagation = False


class DOMMouseEvent(DOMEvent):
    MOUSE_SCROLL_DOWN = 8
    MOUSE_SCROLL_UP = 16

    def __init__(self, target: 'DOMElement', position: Position, buttons: int, current_target: 'DOMElement'=None):
        super().__init__(DOMEventType.MOUSE, target, current_target)
        self.position = position
        self.buttons = buttons

    def is_left_click(self):
        return (self.buttons & MouseEvent.LEFT_CLICK) == MouseEvent.LEFT_CLICK

    def is_right_click(self):
        return (self.buttons & MouseEvent.DOUBLE_CLICK) == MouseEvent.DOUBLE_CLICK

    def is_double_click(self):
        return (self.buttons & MouseEvent.RIGHT_CLICK) == MouseEvent.RIGHT_CLICK

    def is_scroll_down(self):
        return (self.buttons & DOMMouseEvent.MOUSE_SCROLL_DOWN) == DOMMouseEvent.MOUSE_SCROLL_DOWN

    def is_scroll_up(self):
        return (self.buttons & DOMMouseEvent.MOUSE_SCROLL_UP) == DOMMouseEvent.MOUSE_SCROLL_UP


class DOMKeyboardEvent(DOMEvent):
    def __init__(self, target: 'DOMElement', key_code: int, current_target: 'DOMElement'=None):
        super().__init__(DOMEventType.KEYBOARD, target, current_target)
        self.key_code = key_code


class DOMResizeEvent(DOMEvent):
    def __init__(self, target: 'DOMElement', resize_axis: Resize, current_target: 'DOMElement'=None):
        super().__init__(DOMEventType.RESIZE, target, current_target)
        self.resize_axis = resize_axis