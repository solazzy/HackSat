import asyncio
import atexit
import logging
import struct
from enum import Enum
from typing import Optional, Union, Set, List

from asciimatics.event import KeyboardEvent, MouseEvent
from asciimatics.screen import Screen

from rbs_tui_dom.event_emitter import EventEmitter, EventObserver
from rbs_tui_dom.dom.event import DOMEventType, DOMEvent, DOMMouseEvent, DOMKeyboardEvent, \
    DOMResizeEvent
from rbs_tui_dom.dom.style import DOMSize, Display, DOMStyle, Color
from rbs_tui_dom.dom.types import HORIZONTAL, VERTICAL, Position, FULL_WIDTH, FULL_HEIGHT, Resize


class DOMInputType(Enum):
    MOUSE = "mouse"
    KEYBOARD = "keyboard"


class DOMInputKey:
    KEY_ENTER = 10

    KEY_HOME = -200
    KEY_END = -201

    KEY_ARROW_UP = -204
    KEY_ARROW_DOWN = -206
    KEY_ARROW_LEFT = -203
    KEY_ARROW_RIGHT = -205

    KEY_PAGE_UP = -207
    KEY_PAGE_DOWN = -208

    KEY_DELETE = -102
    KEY_BACKSPACE = -300

    KEY_CLEAR_LINE = 21           # ctrl + u
    KEY_CLEAR_WORD_FORWARD = -1   # ctrl + ?
    KEY_CLEAR_WORD_BACKWARD = 23  # ctrl + w
    KEY_CLEAR_LINE_FORWARD = 11   # ctrl + k
    KEY_CLEAR_LINE_BACKWARD = -1  # ctrl + ?

    KEY_MOVE_WORD_FORWARD = 102   # ⌥ + arrow right
    KEY_MOVE_WORD_BACKWARD = 98   # ⌥ + arrow left
    KEY_MOVE_WORD_FORWARD_1 = 6   # ctrl + f
    KEY_MOVE_WORD_BACKWARD_1 = 2  # ctrl + b
    KEY_MOVE_LINE_FORWARD = 1     # ctrl + e
    KEY_MOVE_LINE_BACKWARD = 5    # ctrl + a

    def __init__(self, key: int, special: bool):
        self.key = key
        self.special = special

    def is_char(self):
        return not self.special and 32 <= self.key <= 126

    def char(self):
        return chr(self.key)


class DOMInput(EventEmitter):
    def __init__(self):
        super().__init__()
        self.screen: Optional[Screen] = None

    def _curses_screen_get_event(self, ):
        """
        Check for an event without waiting. This monkey patch adds support for the mouse
        scroll
        """
        import curses
        # Spin through notifications until we find something we want.
        key = 0
        while key != -1:
            # Get the next key
            key = self.screen._screen.getch()

            if key == curses.KEY_RESIZE:
                # Handle screen resize
                self.screen._re_sized = True
            elif key == curses.KEY_MOUSE:
                # Handle a mouse event
                _, x, y, _, bstate = curses.getmouse()
                buttons = 0
                # Some Linux modes only report clicks, so check for any
                # button down or click events.
                if (bstate & curses.BUTTON1_PRESSED != 0 or
                        bstate & curses.BUTTON1_CLICKED != 0):
                    buttons |= MouseEvent.LEFT_CLICK
                if (bstate & curses.BUTTON3_PRESSED != 0 or
                        bstate & curses.BUTTON3_CLICKED != 0):
                    buttons |= MouseEvent.RIGHT_CLICK
                if bstate & curses.BUTTON1_DOUBLE_CLICKED != 0:
                    buttons |= MouseEvent.DOUBLE_CLICK
                if (bstate & curses.A_LOW != 0 or
                        bstate & curses.A_LOW != 0):
                    # scroll down
                    buttons |= DOMMouseEvent.MOUSE_SCROLL_DOWN
                if (bstate & curses.BUTTON4_PRESSED != 0 or
                        bstate & curses.BUTTON4_CLICKED != 0):
                    # scroll up
                    buttons |= DOMMouseEvent.MOUSE_SCROLL_UP
                return MouseEvent(x, y, buttons)
            elif key != -1:
                # Handle any byte streams first
                if self.screen._unicode_aware and key > 0:
                    if key & 0xC0 == 0xC0:
                        self.screen._bytes_to_return = struct.pack(b"B", key)
                        self.screen._bytes_to_read = bin(key)[2:].index("0") - 1
                        continue
                    elif self.screen._bytes_to_read > 0:
                        self.screen._bytes_to_return += struct.pack(b"B", key)
                        self.screen._bytes_to_read -= 1
                        if self.screen._bytes_to_read > 0:
                            continue
                        else:
                            key = ord(self.screen._bytes_to_return.decode("utf-8"))

                # Handle a genuine key press.
                if key in self.screen._KEY_MAP:
                    return KeyboardEvent(self.screen._KEY_MAP[key])
                elif key != -1:
                    return KeyboardEvent(key)

        return None

    def get_event(self):
        raise NotImplementedError()

    def set_screen(self, screen):
        self.screen = screen
        if type(screen).__name__ == "_CursesScreen":
            self.get_event = self._curses_screen_get_event
        else:
            self.get_event = self.screen.get_event

    def add_observer(self, event_type: DOMInputType, observer: EventObserver) -> 'DOMInput':
        super().add_observer(event_type.value, observer)
        return self

    def remove_observer(self, event_type: DOMInputType, observer: EventObserver) -> 'DOMInput':
        super().remove_observer(event_type.value, observer)
        return self

    def check_value(self):
        special = False
        events = []
        while self.screen is not None:
            event = self.get_event()
            if event is None:
                break
            elif isinstance(event, KeyboardEvent):
                if event.key_code == -1:
                    special = True
                    continue
                events.append((DOMInputType.KEYBOARD.value, event.key_code, special))
            elif isinstance(event, MouseEvent):
                events.append((DOMInputType.MOUSE.value, (event.x, event.y), event.buttons))
            special = False

        for event in events:
            self.emit(*event)

class DOMScreen:
    """ Represents a part of the screen on which a DOMElement can be rendered"""
    def __init__(
        self,
        size: DOMSize,
        position: Position,
        offset: Position=(0, 0)
    ):
        self.size = size
        self.position = position
        self.offset = offset

    def contains_position(self, position: Position):
        return self._contains_position(position, HORIZONTAL) and \
               self._contains_position(position, VERTICAL)

    def _contains_position(self, value: Position, orientation: int):
        return self.position[orientation] <= value[orientation] <= \
               self.position[orientation] + self.size[orientation]

    def width(self):
        return self.size[HORIZONTAL]

    def height(self):
        return self.size[VERTICAL]

    def is_visible(self):
        return self.width() > 0 and self.height() > 0

    def __str__(self):
        return "Screen{size=%s, position=%s, offset=%s}" % (self.size, self.position, self.offset)

    def __eq__(self, other):
        if not isinstance(other, DOMScreen):
            return False
        return other.size == self.size and other.position == self.position and other.offset == self.offset


class DOMElement(EventEmitter):
    def __init__(
        self,
        id: str=None,
        classnames: Set[str]=None,
        style: DOMStyle=DOMStyle(),
    ):
        super().__init__()
        self.id = id
        self.debug_id = None
        self.logger = None
        self.classnames = classnames or set()
        self.window: DOMWindow = None
        self.parent: Optional[DOMElement] = None
        self._parent_index: Optional[int] = None
        self.style = style
        self._computed_style = style
        self._original_style: DOMStyle = style
        self.focused = False
        self._desired_size: DOMSize = None
        self._render_style: DOMStyle = None
        self._render_screen: DOMScreen = None
        self._render_full_size: DOMSize = None
        self._render_force = False
        self.add_observer(DOMEventType.BLUR, self._on_blur)
        self.add_observer(DOMEventType.FOCUS, self._on_focus)

    def query_selector(self, name) -> Optional['DOMElement']:
        results = []
        self._query_selector(name, results, True)
        if len(results) > 0:
            return results[0]
        return None

    def query_selector_all(self, name) -> List['DOMElement']:
        results = []
        self._query_selector(name, results, False)
        return results

    def _query_selector(self, name: str, matches: List['DOMElement'], match_one: bool) -> bool:
        if name not in self.classnames:
            return False
        matches.append(self)
        return match_one

    def _set_parent(self, parent: Union['DOMElement', 'DOMWindow'], index: Optional[int]):
        if isinstance(parent, DOMElement):
            self._set_parent_style(parent._computed_style)
            self.parent = parent
            self._parent_index = index
            self.window = parent.window
            self.debug_id = self.id or "%s[%s].%s" % (parent.id, index, type(self).__name__)
        else:
            self.debug_id = self.id or "root"
            self.window = parent

        self.logger = logging.getLogger("dom." + self.debug_id)
        if self.window is not None:
            self.window._register_element(self)

    def _unset_parent(self):
        self.window._unregister_element(self)
        self.parent = None
        self.window = None

    def add_observer(self, event_type: DOMEventType, observer: EventObserver):
        super().add_observer(event_type.value, observer)

    def remove_observer(self, event_type: DOMEventType, observer: EventObserver):
        super().add_observer(event_type.value, observer)

    def find_descendant_at_position(self, position: Position) -> 'DOMElement':
        return self

    def _contains_position(self, position: Position):
        result = self._render_screen.contains_position(position)
        return result

    def set_style(self, style: DOMStyle, render=True) -> 'DOMElement':
        self.style = DOMStyle.merge(self.style, style)
        merged_style = DOMStyle.merge(self._computed_style, self.style)
        return self._update_style(merged_style, render)

    def _set_parent_style(self, style: DOMStyle, render=True):
        merged_style = DOMStyle.merge(style, self.style)
        return self._update_style(merged_style, render)

    def _update_style(self, computed_style, render=True):
        # Use the element's style to override the provided style
        resize = None
        force = False

        # The parent may need to be involved
        if computed_style.size != self._computed_style.size:
            resize = True, True
        # The parent has to be involved when the display property is changed
        if computed_style.display != self._computed_style.display:
            resize = True, True
            force = True
        self._computed_style = computed_style
        if render:
            self._rerender(force, resize=resize)
        elif resize:
            self._desired_size = None
        return self

    def is_displayed(self):
        return self._computed_style.display is not Display.NONE

    def get_desired_size(self, max_size: DOMSize, force=False):
        if not force and self._desired_size is not None:
            return self._desired_size
        self._desired_size = self._calculate_desired_size(max_size)
        return self._desired_size

    def _calculate_styled_size(self, size: DOMSize) -> DOMSize:
        if size is None:
            raise ValueError("The layout's child should define its own size")

        if self._computed_style.display == Display.NONE:
            return size
        child_size = list(size)
        if child_size[0] != FULL_WIDTH:
            child_size[0] += self._computed_style.margin.left + self._computed_style.margin.right

        if child_size[1] != FULL_HEIGHT:
            child_size[1] += self._computed_style.margin.top + self._computed_style.margin.bottom
        return child_size[0], child_size[1]

    def _calculate_styled_screen(self, screen: DOMScreen):
        return DOMScreen(
            (
                screen.size[0] - self._computed_style.margin.left - self._computed_style.margin.right,
                screen.size[1] - self._computed_style.margin.top - self._computed_style.margin.bottom
            ),
            (
                screen.position[0] + self._computed_style.margin.left,
                screen.position[1] + self._computed_style.margin.top
            ),
            screen.offset
        )

    def _calculate_desired_size(self, max_size: DOMSize) -> DOMSize:
        """
        Calculate the desired size for the DOMLayout. The size can be defined via the style
        property or it can be defined by the DOMElement implementation. The desired size include
        margins and padding.
        """
        if self._computed_style.display is Display.NONE:
            size = 0, 0
        elif self._computed_style.size[0] and self._computed_style.size[1]:
            size = self._calculate_styled_size(self._computed_style.size)
        else:
            raise ValueError("The DOM element does not define a size")
        self._desired_size = size
        return size

    def _should_render(self, screen: DOMScreen, force: bool=False) -> bool:
        return force or self._render_force or \
            screen != self._render_screen or \
            self._computed_style != self._render_style or \
            self._desired_size != self._render_full_size

    def _can_display(self, screen: DOMScreen) -> bool:
        return self.window is not None and screen.is_visible()

    def _rerender(self, force: bool = False, resize: Resize = None, refresh_screen: bool = True):
        # This can happen when configuring a DOMElement that has yet to be added to the window
        if not self.window:
            return
        self.logger.debug(f"rerendering with resize {resize}")
        self._render_force = True

        # See if the resize requires the parent to be rerendered
        if resize is not None and (resize[HORIZONTAL] or resize[VERTICAL]) and \
                self.window.root_element != self:
            # Only resize the parent if one of the axis' size is set to grow with the
            # content (=None)
            parent_resize = (
                resize[0] and self._computed_style.size[0] is None,
                resize[1] and self._computed_style.size[1] is None
            )
            if force or parent_resize[0] or parent_resize[1]:
                # Remove the desired size from the cache since it changed
                self._desired_size = None
                self.emit(
                    DOMEventType.RESIZE.value,
                    DOMResizeEvent(self, (parent_resize[0], parent_resize[1]))
                )
                return False
        if not self._render_screen:
            # The element was not previously rendered, let the parent take care of it
            self.emit(DOMEventType.RESIZE.value, DOMResizeEvent(self, (True, True)))
            return False
        self._render(self._render_screen, force)
        if refresh_screen:
            self.window.screen.refresh()
        return True

    def _render(self, screen: DOMScreen, force: bool = False):
        self.logger.debug(f"rendering on screen {screen}")
        self._render_force = False
        self._render_screen = screen
        self._render_style = self._computed_style
        if not self.is_displayed():
            self._render_full_size = None
            self._render_screen = None
            self._render_style = None

    def _mouse_event(self, position: Position, buttons: int):
        self.emit(DOMEventType.MOUSE.value, DOMMouseEvent(self, position, buttons))
        if not self.window._disable_click and buttons:
            self.focus()

    def _on_blur(self, event: DOMEvent):
        self.focused = False

    def _on_focus(self, event: DOMEvent):
        self.focused = True

    def focus(self):
        if not self.window or self.window.focused_element is self:
            return
        self.focused = True
        self.window._set_focus(self)
        self.window.input.add_observer(DOMInputType.KEYBOARD, self._key_press)
        self.emit(DOMEventType.FOCUS.value, DOMEvent(DOMEventType.FOCUS, self))

    def blur(self):
        if not self.focused:
            return
        self.focused = False
        self.window._set_blur()
        self.window.input.remove_observer(DOMInputType.KEYBOARD, self._key_press)
        self.emit(DOMEventType.BLUR.value, DOMEvent(DOMEventType.BLUR, self))

    def _key_press(self, key_code: int, special: bool):
        self.emit(DOMEventType.KEYBOARD.value, DOMKeyboardEvent(self, key_code))

    def _clear(self, screen: DOMScreen):
        if self.window is None or screen is None or \
                screen.size[HORIZONTAL] <= 0 or screen.size[VERTICAL] <= 0:
            return
        initial_x = screen.position[HORIZONTAL]
        initial_y = screen.position[VERTICAL]
        text = " " * screen.size[HORIZONTAL]
        for initial_y in range(initial_y, initial_y + screen.size[VERTICAL]):
            self.window.screen.print_at(
                text,
                initial_x,
                initial_y,
                bg=self._computed_style.background.value if self._computed_style.background
                    else Color.WHITE.value,
            )


class CLIWindowExit(Exception):
    pass


class DOMWindow:
    def __init__(self, disable_click=False):
        self.input = DOMInput()
        self.input.add_observer(DOMInputType.MOUSE, self._on_mouse_event)
        self.event_loop = asyncio.get_event_loop()
        self.screen: Optional[Screen] = None
        self.root_element: Optional[DOMElement] = None
        self.focused_element: Optional[DOMElement] = None
        self.logger = logging.getLogger("window")
        self._elements = {}
        self._disable_click = disable_click
        self._ready = asyncio.Event()

    async def run(self, root_element: DOMElement=None):
        asyncio.get_event_loop().create_task(self._run(root_element))
        await self._ready.wait()

    def get_element_by_id(self, id: str) -> DOMElement:
        return self._elements[id]

    async def _run(self, root_element: DOMElement = None):
        if root_element is None:
            raise ValueError("The root element must be set")

        atexit.register(lambda: self._exit())

        self.screen = Screen.open()
        self.input.set_screen(self.screen)
        self.root_element = root_element
        self.root_element._set_parent(self, None)
        self.root_element.focus()
        self.render(True)
        self._ready.set()
        while True:
            if not self.screen:
                break
            if self.screen.has_resized():
                self.render()
            await asyncio.sleep(0.01)
            try:
                self.input.check_value()
            except CLIWindowExit:
                self._exit()
                break
            except Exception as e:
                self._exit()
                logging.error("Fatal error", exc_info=True)

    def render(self, force: bool = False) -> 'DOMWindow':
        dimensions = self._get_screen_dimensions()
        if not force and dimensions[HORIZONTAL] == self.screen.width and \
                dimensions[VERTICAL] == self.screen.height:
            return self
        self.screen.width = dimensions[HORIZONTAL]
        self.screen.height = dimensions[VERTICAL]
        self.screen.clear()
        self.root_element._render(DOMScreen(
            size=dimensions,
            position=(0, 0)
        ), True)
        self.screen.refresh()
        return self

    def _exit(self):
        if not self.screen:
            return
        try:
            self.screen._clear()
            self.screen.close()
            self.screen = None
            self.input.screen = None
        except:
            try:
                import curses
                curses.endwin()
            except:
                pass

    def _set_blur(self):
        self.focused_element = None

    def _set_focus(self, element: DOMElement):
        if self.focused_element is not None:
            self.focused_element.blur()
        self.focused_element = element

    def _on_mouse_event(self, position: Position, buttons: int):
        try:
            child = self.root_element.find_descendant_at_position(position)
            if child is None:
                logging.error("Could not find a child for mouse event at position")
                return
            child._mouse_event(position, buttons)
        except:
            logging.error("Failed", exc_info=True)

    def _get_screen_dimensions(self):
        return self.screen._screen.getmaxyx()[1], self.screen._screen.getmaxyx()[0]

    def _register_element(self, dom_element: DOMElement):
        if dom_element.id is None:
            return
        self._elements[dom_element.id] = dom_element

    def _unregister_element(self, dom_element: DOMElement):
        if dom_element.id is None:
            return
        if not dom_element.id in self._elements:
            logging.error("The dom element %s was not registered on the window" % dom_element.id)
            return
        if self._elements[dom_element.id] is dom_element:
            del self._elements[dom_element.id]
        self._elements[dom_element] = dom_element