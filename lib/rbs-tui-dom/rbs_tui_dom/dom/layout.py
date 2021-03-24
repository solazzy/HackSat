import math
from typing import List, Optional, Union, Set, Tuple

from asciimatics.screen import Screen

from rbs_tui_dom.dom import DOMSize, DOMScreen, DOMElement, DOMWindow, VERTICAL, Position, \
    DOMEventType, \
    DOMEvent, DOMKeyboardEvent, DOMResizeEvent, DOMMouseEvent
from rbs_tui_dom.dom.style import DOMStyle, Display, Scroll
from rbs_tui_dom.dom.types import FULL_LENGTH, Orientation, HORIZONTAL

SCROLL_LINE = 0
SCROLL_WIDGET = 1
CLIScroll = int

LEFT_TO_RIGHT = TOP_TO_BOTTOM = 0
RIGHT_TO_LEFT = BOTTOM_TO_TOP = 1
CLIDirection = int


class DOMLayout(DOMElement):
    """ A DOMElement that can contain children"""
    def __init__(
        self,
        id: str=None,
        classnames: Set[str] = None,
        style: DOMStyle=DOMStyle(),
        children: List[DOMElement]=None,
    ):
        super().__init__(id=id, classnames=classnames, style=style)
        self._children: List[DOMElement] = []
        self._children_positions = []
        self.set_children(children or [])

    def _query_selector(self, name: str, matches: List['DOMElement'], match_one=True) -> bool:
        if super()._query_selector(name, matches, match_one):
            return True

        for child in self._children:
            if child._query_selector(name, matches, match_one):
                return True

        return False

    def _set_parent(self, parent: Union['DOMElement', 'DOMWindow'], index: int):
        super()._set_parent(parent, index)
        for i, child in enumerate(self._children):
            child._set_parent(self, i)

    def _unset_parent(self):
        super()._unset_parent()
        for child in self._children:
            child._unset_parent()

    def _set_parent_style(self, style: DOMStyle, render=True):
        computed_style = DOMStyle.merge(style, self.style)
        for child in self._children:
            child._set_parent_style(computed_style, False)
        super()._update_style(computed_style, render)

    def set_style(self, style: DOMStyle, render=True):
        self.style = DOMStyle.merge(self.style, style)
        computed_style = DOMStyle.merge(self._computed_style, self.style)
        for child in self._children:
            child._set_parent_style(computed_style, False)
        super()._update_style(computed_style, render)

    def add_child(self, element: DOMElement, index: int=None) -> 'DOMLayout':
        """ Add a child to the DOMLayout. The child is rendered immediately"""
        if index is None:
            index = len(self._children)

        self._children.insert(index, element)
        element._set_parent(self, index)
        element.add_observer(DOMEventType.RESIZE, self._on_child_resize)
        element.add_global_observer(self._on_child_event)

        self._rerender(resize=(True, True))
        return self

    def add_children(self, elements: List[DOMElement]):
        index = len(self._children)
        for i, element in enumerate(elements):
            self._children.append(element)
            element._set_parent(self, index + i)
            element.add_observer(DOMEventType.RESIZE, self._on_child_resize)
            element.add_global_observer(self._on_child_event)
        self._rerender(resize=(True, True))
        return self

    def remove_child(self, index: int) -> 'DOMLayout':
        """ Remove a child from the DOMLayout. The child is unrendered immediately"""
        element = self._children[index]
        del self._children[index]
        del self._children_positions[index]
        element.remove_observer(DOMEventType.RESIZE, self._on_child_resize)
        element.remove_global_observer(self._on_child_event)

        self._rerender(resize=(True, True))
        return self

    def set_children(self, children: List[DOMElement]) -> 'DOMLayout':
        """ Override the children of the DOMLayout. The children are rendered immediately"""
        for element in self._children:
            element.remove_global_observer(self._on_child_event)
        for i, element in enumerate(children):
            element._set_parent(self, i)
            element.add_global_observer(self._on_child_event)

        self._children = children
        self._rerender(resize=(True, True))
        return self

    def _on_child_event(self, event: DOMEvent):
        """ Bubble up all the child events """
        if event.event_type is DOMEventType.RESIZE:
            self._on_child_resize(event)
            return

        if event.stop_propagation:
            return
        event.current_target = self
        self.emit(event.event_type.value, event)

    def _on_child_resize(self, event: DOMResizeEvent):
        """ Handle the child resize event. The layout will determine if its own size would change and either rerender
        itself or bubble the event.
        """
        self._rerender(resize=event.resize_axis)


class DOMStackLayout(DOMLayout):
    def __init__(
        self,
        id: str=None,
        classnames: Set[str]=None,
        style: DOMStyle=DOMStyle(),
        orientation: Orientation=VERTICAL,
        children: List[DOMElement]=None,
    ):
        self.orientation = orientation
        self.orientation_name = "vertical" if orientation == VERTICAL else "horizontal"
        self.opposite_orientation = (orientation + 1) % 2
        self._focused_child_index = None
        super().__init__(id=id, style=style, children=children, classnames=classnames)
        self.add_observer(DOMEventType.KEYBOARD, self._on_keyboard_event)
        self.add_observer(DOMEventType.MOUSE, self._on_mouse_event)

    def _on_child_event(self, event: DOMEvent):
        if event.event_type is DOMEventType.FOCUS and self._render_full_size is not None and  \
                self._computed_style.scroll == Scroll.CHILD:
            self._ensure_focus_visible(self._children.index(event.current_target))
        super()._on_child_event(event)

    def _on_mouse_event(self, mouse_event: DOMMouseEvent):
        if mouse_event.is_scroll_down():
            self._move(1, VERTICAL, mouse_event)
        elif mouse_event.is_scroll_up():
            self._move(-1, VERTICAL, mouse_event)

    def _on_keyboard_event(self, keyboard_event: DOMKeyboardEvent):
        key_code = keyboard_event.key_code
        if key_code == Screen.KEY_DOWN:
            self._move(1, VERTICAL, keyboard_event)
        elif key_code == Screen.KEY_UP:
            self._move(-1, VERTICAL, keyboard_event)
        elif key_code == Screen.KEY_RIGHT:
            self._move(4, HORIZONTAL, keyboard_event)
        elif key_code == Screen.KEY_LEFT:
            self._move(-4, HORIZONTAL, keyboard_event)
        if key_code == Screen.KEY_PAGE_DOWN:
            self._move(self._render_screen.height(), VERTICAL, keyboard_event)
        elif key_code == Screen.KEY_PAGE_UP:
            self._move(-self._render_screen.height(), VERTICAL, keyboard_event)

    def _move(self, offset: int, orientation: int, event: DOMEvent):
        self.logger.debug(
            f"Responding to potential scroll. "
            f"Rendered size: {self._render_full_size}, "
            f"Screen size: {self._render_screen.size}"
        )
        if self._render_full_size[self.orientation] <= self._render_screen.size[self.orientation] and \
                self.style.scroll != Scroll.CHILD:
            self.logger.debug("Not responding to potential scroll. The content fits")
            return
        if self._computed_style.size[self.orientation] is None:
            self.logger.debug("Not responding to potential scroll. The div has no length" )
            return

        if self._computed_style.scroll is None or self._computed_style.scroll == Scroll.LINE:
            return self._move_by_line(offset, orientation, event)
        elif self._computed_style.scroll == Scroll.CHILD:
            # Can't move by child in that direction, bubble
            if orientation != self.orientation:
                return
            return self._move_by_child(offset, event)

    def _render_move(self, screen_offset: Tuple[int, int]):
        self.logger.debug(
            f"The screen offset was {self._render_screen.offset}. New offset: {screen_offset}"
        )
        self._render(DOMScreen(
            self._render_screen.size,
            self._render_screen.position,
            (screen_offset[0], screen_offset[1])
        ))
        self.window.screen.refresh()

    def move_min(self, orientation: int):
        min_offset = -self._render_full_size[orientation] + self._render_screen.size[orientation]
        if self._render_screen.offset[orientation] == min_offset:
            return
        screen_offset = list(self._render_screen.offset)
        screen_offset[orientation] = min_offset
        self._render_move((screen_offset[0], screen_offset[1]))

    def move_max(self, orientation: int):
        max_offset = 0
        if self._render_screen.offset[orientation] == max_offset:
            return
        screen_offset = list(self._render_screen.offset)
        screen_offset[orientation] = max_offset
        self._render_move((screen_offset[0], screen_offset[1]))

    def _move_by_line(self, offset: int, orientation: int, event: DOMEvent):
        max_offset = 0
        min_offset = -self._render_full_size[orientation] + self._render_screen.size[orientation]
        i_offset = min(
            max_offset,
            max(min_offset, self._render_screen.offset[orientation] - offset)
        )
        # The move wouldn't change the scroll offset, let the event bubble up
        if i_offset == self._render_screen.offset[orientation]:
            return
        event.stop_propagation = True
        screen_offset = list(self._render_screen.offset)
        screen_offset[orientation] = i_offset
        self._render_move((screen_offset[0], screen_offset[1]))

    def _move_by_child(self, offset: int, event: DOMEvent):
        event.stop_propagation = True
        if len(self._children) == 0:
            return
        if self._focused_child_index is None:
            if offset >= 0:
                self._children[0].focus()
            if offset < 0:
                self._children[-1].focus()
        else:
            # TODO: Bubble if the top/bottom is reached
            self._children[max(0, min(len(self._children) - 1, self._focused_child_index + offset))].focus()

    def _ensure_focus_visible(self, index: int):
        if not self._render_screen:
            return
        if index == self._focused_child_index:
            return

        self._focused_child_index = index
        child = self._children[index]
        child_desired_size = child.get_desired_size()
        top_max_offset = -self._children_positions[index]
        bottom_min_offset = self._render_screen.size[self.orientation] - \
            (self._children_positions[index] + child_desired_size[self.orientation])

        offset = None
        self.logger.debug("Child screen: %s" % child._render_screen)
        self.logger.debug(
            "Setting selection from %s to %s. Bottom min: %s, Top max %s" %
            (self._focused_child_index, index, bottom_min_offset, top_max_offset)
        )
        if bottom_min_offset < self._render_screen.offset[self.orientation]:
            offset = list(self._render_screen.offset)
            offset[self.orientation] = bottom_min_offset
        elif top_max_offset > self._render_screen.offset[self.orientation]:
            offset = list(self._render_screen.offset)
            offset[self.orientation] = top_max_offset

        if offset is not None:
            self.logger.debug(
                "Updating the offset to scroll. Offset: %s, %s" %
                (offset[0], offset[1])
            )
            self._render(DOMScreen(
                self._render_screen.size,
                self._render_screen.position,
                (offset[0], offset[1])
            ))
            self.window.screen.refresh()

    def find_descendant_at_position(self, position: Position) -> Optional['DOMElement']:
        if not self._contains_position(position) or len(self._children) == 0:
            return None
        child_index = self.find_child_index_at_position(position[self.orientation])
        child = self._children[child_index]
        if child._computed_style.display is Display.NONE:
            return self
        elif isinstance(child, DOMLayout):
            return child.find_descendant_at_position(position)
        elif child._contains_position(position):
            return child
        else:
            return self

    def find_child_index_at_position(self, position: int, relative: bool=False, left: int=None, right: int=None):
        if left is None or right is None:
            if not relative:
                position = position - (self._render_screen.position[self.orientation] +
                    self._render_screen.offset[self.orientation])
            return self.find_child_index_at_position(
                position,
                relative,
                0,
                len(self._children_positions) - 1
            )
        if left <= right:
            mid = math.floor(left + (right - left) / 2)
            if self._children_positions[mid] == position:
                for index in range(left, right + 1):
                    self.logger.debug(index)
                    if self._children_positions[index] == position and \
                            self._children[index]._computed_style.display != Display.NONE:
                        return index
                return mid
            elif self._children_positions[mid] > position:
                return self.find_child_index_at_position(position, relative, left, mid - 1)
            else:
                return self.find_child_index_at_position(position, relative, mid + 1, right)
        else:
            return max(0, min(len(self._children) - 1, right))

    def _calculate_desired_size(self, max_size: DOMSize) -> DOMSize:
        try:
            return super()._calculate_desired_size(max_size)
        except ValueError:
            pass

        size = [
            self._computed_style.size[0] if self._computed_style.size[0] is not None else 0,
            self._computed_style.size[1] if self._computed_style.size[1] is not None else 0,
        ]
        for child in self._children:
            child_size = child.get_desired_size(max_size)
            if self._computed_style.size[self.opposite_orientation] is None:
                # If the child is full length in the opposite direction, override the computed style
                if child_size[self.opposite_orientation] == FULL_LENGTH:
                    size[self.opposite_orientation] = FULL_LENGTH
                # Only add to the length in the opposite direction if its not full length already
                elif size[self.opposite_orientation] != FULL_LENGTH:
                    size[self.opposite_orientation] += child_size[self.opposite_orientation]
            if self._computed_style.size[self.orientation] is None:
                if child_size[self.orientation] == FULL_LENGTH:
                    size[self.orientation] = FULL_LENGTH
                elif size[self.orientation] != FULL_LENGTH:
                    size[self.orientation] += child_size[self.orientation]
        return self._calculate_styled_size((size[0], size[1]))

    def _should_render(self, screen: DOMScreen, force: bool = False) -> bool:
        return super()._should_render(screen, force) or any([
            # The render screen wouldn't change unless the layout itself has to rerender
            child._should_render(child._render_screen, force)
            for child in self._children
        ])

    def _render(self, screen: DOMScreen, force: bool = False):
        if not self._should_render(self._render_screen, force):
            super()._render(screen)
            return
        if not self._can_display(screen):
            # Let the children know that they are no longer being displayed so they can rerender
            # properly when the layout is displayed again
            for child in self._children:
                child._render(screen)
            super()._render(screen)
            return

        self._children_positions = []
        self.logger.debug("rendering on %s" % screen)
        length = 0
        full_length_widgets = 0
        last_full_length_widget = None
        children_desired_size = []
        for child in self._children:
            child_desired_size = child.get_desired_size(screen.size)
            # Account for the child's margin when computing sizes
            children_desired_size.append(child_desired_size)
            if child_desired_size[self.orientation] is FULL_LENGTH:
                full_length_widgets += 1
                last_full_length_widget = child
            else:
                length += child_desired_size[self.orientation]
        total_shared_length = max(screen.size[self.orientation] - length, 0)
        shared_length = int(total_shared_length / (full_length_widgets or 1))
        extra_shared_length = total_shared_length - shared_length * full_length_widgets

        if length + shared_length * full_length_widgets <= screen.size[self.orientation]:
            # The layout element can render all the children, reset the scroll offset
            screen.offset = list(screen.offset)
            screen.offset[self.orientation] = 0
            screen.offset = (screen.offset[0], screen.offset[1])

        child_position = screen.offset[self.orientation]

        render_size = [0, 0]
        for child, child_desired_size in zip(self._children, children_desired_size):
            if child_desired_size[self.orientation] is not FULL_LENGTH:
                child_position += self._render_child(
                    screen,
                    child,
                    child_position,
                    child_desired_size,
                    force
                )
            else:
                new_size = list(child_desired_size)
                new_size[self.orientation] = shared_length
                if child is last_full_length_widget:
                    new_size[self.orientation] += extra_shared_length
                child_position += self._render_child(
                    screen,
                    child,
                    child_position,
                    (new_size[0], new_size[1]),
                    force
                )
            # Handle the case in which the child was not rendered
            if child._render_full_size is not None:
                render_size[self.opposite_orientation] = max(
                    child._render_full_size[self.opposite_orientation],
                    render_size[self.opposite_orientation]
                )

        if self._children:
            render_size[self.orientation] = child_position - screen.offset[self.orientation]

        clear_size = [0, 0]
        clear_size[self.orientation] = max(0, screen.size[self.orientation] - max(0, child_position))
        clear_size[self.opposite_orientation] = screen.size[self.opposite_orientation]
        clear_position = [0, 0]
        clear_position[self.orientation] = screen.position[self.orientation] + max(0, child_position)
        clear_position[self.opposite_orientation] = screen.position[self.opposite_orientation]
        clear_screen = DOMScreen(
            size=(clear_size[0], clear_size[1]),
            position=(clear_position[0], clear_position[1])
        )
        self._clear(clear_screen)
        self._render_full_size = render_size
        super()._render(screen)

    def _render_child(
            self,
            screen: DOMScreen,
            child_element: DOMElement,
            child_position: int,
            child_desired_size: DOMSize,
            force: bool = False
    ) -> int:
        length = min(
            child_desired_size[self.orientation] + min(child_position, 0),
            screen.size[self.orientation] - max(child_position, 0)
        )
        self._children_positions.append(child_position - screen.offset[self.orientation])
        screen_size = list(screen.size)
        screen_size[self.orientation] = max(length, 0)
        position = list(screen.position)
        # Min is for making sure the position does not overflow the screen
        position[self.orientation] = min(
            # The max is for making the position does not underflow the screen
            screen.position[self.orientation] + max(child_position, 0),
            screen.size[self.orientation] + screen.position[self.orientation]
        )
        offset = list(screen.offset)
        offset[self.orientation] = min(child_position, 0)
        offset[self.opposite_orientation] = screen.offset[self.opposite_orientation]
        child_screen = DOMScreen(
            size=(
                max(0, screen_size[0] - child_element.style.margin.left - child_element.style.margin.right),
                max(0, screen_size[1] - child_element.style.margin.top - child_element.style.margin.bottom)
            ),
            position=(
                position[0] + child_element.style.margin.left,
                position[1] + child_element.style.margin.top
            ),
            offset=(offset[0], offset[1])
        )
        # Clear the margins
        child_element._render(child_screen, force)
        if child_element.is_displayed():
            left_screen = DOMScreen(
                size=(child_element.style.margin.left, screen_size[1]),
                position=(position[0], position[1])
            )
            right_screen = DOMScreen(
                size=(child_element.style.margin.right, screen_size[1]),
                position=(position[0] + screen_size[0] - child_element.style.margin.right, position[1])
            )
            top_screen = DOMScreen(
                size=(screen_size[1], child_element.style.margin.top),
                position=(position[0], position[1])
            )
            bottom_screen = DOMScreen(
                size=(screen_size[1], child_element.style.margin.bottom),
                position=(position[0], position[1] + screen_size[1] - child_element.style.margin.bottom)
            )
            self._clear(left_screen)
            self._clear(right_screen)
            self._clear(top_screen)
            self._clear(bottom_screen)
        return child_desired_size[self.orientation]