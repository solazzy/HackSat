from typing import Union, List, Set, Optional

from rbs_tui_dom.dom import DOMSize, DOMScreen, DOMElement, HORIZONTAL, VERTICAL, DOMStyle, \
    DOMEvent, DOMInputKey
from rbs_tui_dom.dom.style import Color, Alignment


class DOMText(DOMElement):
    def __init__(
        self,
        value: Union[List[str], str] = "",
        id: str = None,
        classnames: Set[str] = None,
        style: DOMStyle=DOMStyle(),
    ):
        self.values: List[str] = value if isinstance(value, list) else [value]
        self._render_values = None
        super().__init__(id=id, style=style, classnames=classnames)

    def set_value(self, value: Union[List[str], str]) -> 'DOMText':
        new_values = value if isinstance(value, list) else [value]
        resize = [True, True]
        if self.values is not None:
            if len(new_values) == len(self.values):
                resize[1] = False
            if max([len(v) for v in new_values]) == max([len(v) for v in self.values]):
                resize[0] = False
        self.values = new_values
        self._rerender(resize=(resize[0], resize[1]))
        return self

    def _calculate_desired_size(self, max_size: DOMSize) -> DOMSize:
        try:
            return super()._calculate_desired_size(max_size)
        except ValueError:
            pass

        self._desired_size = self._calculate_styled_size((
            self._computed_style.size[0] if self._computed_style.size[0] is not None
                else max([len(v) for v in self.values]),
            self._computed_style.size[1] if self._computed_style.size[1] is not None
                else len(self.values),
        ))
        return self._desired_size

    def _should_render(self, screen: DOMScreen, force: bool=False) -> bool:
        return super()._should_render(screen, force) or (self._render_values != self.values)

    def _render(self, screen: DOMScreen, force: bool = False):
        if not self._should_render(screen, force) or not self._can_display(screen):
            super()._render(screen)
            return

        self._display_lines(self._format_lines(self.values, screen), screen)
        self._render_values = self.values
        self._render_full_size = self.get_desired_size(screen.size)
        super()._render(screen)

    def _format_lines(self, lines: List[str], screen: DOMScreen):
        lines = list(lines)
        if screen.offset[VERTICAL] < 0:
            lines[:abs(screen.offset[VERTICAL])] = []
        lines[screen.size[VERTICAL]:] = []

        formatted_lines = []
        for line in lines:
            if screen.offset[HORIZONTAL] < 0:
                line = line[abs(screen.offset[HORIZONTAL]):]
            line = line[:screen.size[HORIZONTAL]]
            if self._computed_style.text_align is None or \
                    self._computed_style.text_align is Alignment.LEFT:
                formatted_lines.append(line.ljust(screen.size[HORIZONTAL]))
            elif self._computed_style.text_align is Alignment.RIGHT:
                formatted_lines.append(line.rjust(screen.size[HORIZONTAL]))
            elif self._computed_style.text_align is Alignment.CENTER:
                formatted_lines.append(line.center(screen.size[HORIZONTAL]))
        for i in range(len(lines), screen.size[VERTICAL]):
            formatted_lines.append(" " * screen.size[HORIZONTAL])
        return formatted_lines

    def _display_lines(self, lines: List[str], screen: DOMScreen):
        for index, line in enumerate(lines):
            self.window.screen.print_at(
                line,
                screen.position[HORIZONTAL],
                screen.position[VERTICAL] + index,
                colour=self._computed_style.color.value if self._computed_style.color
                    else Color.WHITE.value,
                bg=self._computed_style.background.value if self._computed_style.background
                else Color.BLACK.value
            )


class DOMTextFill(DOMText):
    def __init__(
        self,
        char: str = " ",
        id: str = None,
        classnames: Set[str] = None,
        style: DOMStyle=DOMStyle(),
    ):
        super().__init__(id=id, style=style, classnames=classnames)
        self.character = char

    def _render(self, screen: DOMScreen, force: bool=False):
        self.values = [self.character * screen.size[HORIZONTAL]] * (screen.size[VERTICAL])
        super()._render(screen, force)


class DOMTextFlex(DOMElement):
    def __init__(
            self,
            value: str = "",
            id: str = None,
            classnames: Set[str] = None,
            style: DOMStyle=DOMStyle(),
    ):
        super().__init__(id=id, style=style, classnames=classnames)
        self._value = value
        self._render_value: Optional[str] = None
        self._static_prefix_length = 0

    def get_value(self) -> str:
        return self._value

    def set_value(self, value: str):
        self._value = value
        self._rerender(resize=(False, True))

    def _should_render(self, screen: DOMScreen, force: bool=False) -> bool:
        return super()._should_render(screen, force) or (self._render_value != self._value)

    def _calculate_desired_size(self, max_size: DOMSize) -> DOMSize:
        try:
            return super()._calculate_desired_size(max_size)
        except ValueError:
            pass

        self._desired_size = self._calculate_styled_size((
            self._computed_style.size[0] if self._computed_style.size[0] is not None
            else len(self._value),
            self._computed_style.size[1] if self._computed_style.size[1] is not None
            else len(self._value) // max_size[HORIZONTAL] + 1,
        ))
        return self._desired_size

    def _render_static_prefix(self, screen: DOMScreen):
        pass

    def _render(self, screen: DOMScreen, force: bool=False):
        if not self._should_render(screen, force) or not self._can_display(screen):
            super()._render(screen)
            return

        for i in range(0, screen.height()):
            line_index = i - screen.offset[VERTICAL]
            value_start = line_index * screen.width()
            line_length = 0
            if line_index == 0:
                self._render_static_prefix(screen)
                value_end = value_start + screen.width() - self._static_prefix_length
                line_length += self._static_prefix_length
            else:
                value_start -= self._static_prefix_length
                value_end = value_start + screen.width()
            value = self._value[value_start:value_end]
            line_length += len(value)
            self.window.screen.print_at(
                value,
                screen.position[HORIZONTAL] if line_index != 0
                    else screen.position[HORIZONTAL] + self._static_prefix_length,
                screen.position[VERTICAL] + i,
                colour=self._computed_style.color.value if self._computed_style.color
                    else Color.WHITE.value,
                bg=self._computed_style.background.value if self._computed_style.background
                    else Color.BLACK.value
            )
            padding_length = screen.width() - line_length
            self.window.screen.print_at(
                " " * padding_length,
                screen.position[HORIZONTAL] + line_length,
                screen.position[VERTICAL] + i,
            )
        self._render_values = self._value
        self._render_full_size = self._desired_size
        super()._render(screen)


class DOMTextInput(DOMElement):
    def __init__(
            self,
            id: str = None,
            classnames: Set[str] = None,
            style: DOMStyle = DOMStyle(),
    ):
        super().__init__(id=id, style=style, classnames=classnames)
        self._cursor_position: int = 0
        self._render_cursor_position: int = 0
        self._value: str = ""
        self._render_value: str = ""
        # This dictates where the value starts to be rendered when it doesn't fully fit
        self._value_offset = 0
        self._static_prefix_length = 0

    def get_value(self) -> str:
        return self._value

    def set_value(self, value: str = "", render: bool = True):
        self._value = value
        self._cursor_position = len(self._value)
        self._value_offset = self._calculate_offset(0)
        if render:
            self._rerender(True, resize=(False, True))

    def _on_focus(self, event: DOMEvent):
        super()._on_focus(event)
        self._rerender(True)

    def _on_blur(self, event: DOMEvent):
        super()._on_blur(event)
        self._rerender(True)

    def _get_line_index(self, screen_size: DOMSize, position: int):
        return position // screen_size[HORIZONTAL]

    def _get_line_position(self,screen_size: DOMSize, position: int):
        return position % screen_size[HORIZONTAL]

    def _get_line_count(self, screen_size: DOMSize, value: str):
        return (len(value) + self._get_static_prefix_size()) // screen_size[HORIZONTAL] + 1

    def _is_short_scroll(self):
        # When the desired size is calculated,
        return self._desired_size is not None and 1 <= self._desired_size[VERTICAL] <= 2

    def _render_static_prefix(self, screen: DOMScreen):
        pass

    def _get_static_prefix_size(self) -> int:
        return self._static_prefix_length

    def _calculate_desired_size(self, max_size: DOMSize) -> DOMSize:
        self._desired_size = self._calculate_styled_size((
            self._computed_style.size[0] if self._computed_style.size[1] else max_size[HORIZONTAL],
            self._computed_style.size[1] if self._computed_style.size[1] is not None
                else min(
                    (len(self._value) + self._get_static_prefix_size()) // max_size[HORIZONTAL] + 1,
                    max_size[VERTICAL]
                )
        ))
        return self._desired_size

    def _calculate_short_scroll_offset(self, prev_cursor_position: int, screen_size: DOMSize):
        # Single line scroll
        cursor_position = self._cursor_position + self._get_static_prefix_size()
        prev_cursor_position += self._get_static_prefix_size()

        display_character_count = screen_size[HORIZONTAL]
        is_truncated_start = self._value_offset != 0
        is_truncated_end = len(self._value) - self._value_offset > \
            display_character_count - self._get_static_prefix_size()
        prev_cursor_line_index = self._get_line_index(
            screen_size,
            prev_cursor_position - self._value_offset,
        )
        next_cursor_line_index = self._get_line_index(
            screen_size,
            cursor_position - self._value_offset,
        )
        next_cursor_line_position = self._get_line_position(
            screen_size,
            cursor_position - self._value_offset,
        )
        if next_cursor_line_position <= self._get_static_prefix_size() and is_truncated_start:
            # Account for the "<" character at the beginning
            prev_cursor_line_index -= 1
        elif next_cursor_line_position == screen_size[HORIZONTAL] - 1 and is_truncated_end:
            # Account for the ">" character at the end
            next_cursor_line_index += 1

        if prev_cursor_line_index != next_cursor_line_index:
            # Single line "scroll". The value is offset such that the cursor is centered
            return max(0, cursor_position -
                (screen_size[HORIZONTAL] + self._get_static_prefix_size()) // 2
            )
        return self._value_offset

    def _calculate_long_scroll_offset(self, prev_cursor_position: int, screen_size: DOMSize):
        # Multi line "scroll". The value is offset such that the cursor is visible
        cursor_position = self._cursor_position + self._get_static_prefix_size()
        prev_cursor_position += self._get_static_prefix_size()

        prev_line_offset = (self._value_offset + self._get_static_prefix_size()) // \
            screen_size[HORIZONTAL]
        prev_cursor_line_index = self._get_line_index(screen_size, prev_cursor_position)

        line_count = self._get_line_count(screen_size, self._value)
        cursor_line_index = self._get_line_index(screen_size, cursor_position)

        if prev_cursor_line_index < cursor_line_index:
            # The cursor is moving to the next line. Calculate the offset so that the cursor
            # is on the first visible line
            if cursor_line_index - prev_line_offset >= screen_size[VERTICAL] - 1:
                return max(
                    0,
                    screen_size[HORIZONTAL] *
                        min(cursor_line_index - 1, line_count - screen_size[VERTICAL])
                        - self._get_static_prefix_size()
                )
        elif prev_cursor_line_index > cursor_line_index:
            # The cursor is moving to the previous line. Calculate the offset such that the
            # cursor is on the second to last visible line
            if cursor_line_index - prev_line_offset < 1:
                # Only change the offset if the line is not being rendered
                return max(
                    0,
                    screen_size[HORIZONTAL] * (cursor_line_index - (screen_size[VERTICAL] - 2))
                        - self._get_static_prefix_size()
                )
        return self._value_offset

    def _calculate_offset(self, prev_cursor_position: int, screen_size: DOMScreen = None):
        if screen_size is None:
            screen_size = self._desired_size
        if screen_size is None:
            return
        if self._is_short_scroll():
            display_character_count = screen_size[HORIZONTAL]
        else:
            display_character_count = screen_size[HORIZONTAL] * screen_size[VERTICAL]
        if len(self._value) + self._get_static_prefix_size() >= display_character_count:
            # The value does not fit on the screen
            if self._is_short_scroll():
                return self._calculate_short_scroll_offset(prev_cursor_position, screen_size)
            else:
                return self._calculate_long_scroll_offset(prev_cursor_position, screen_size)
        return 0

    def _key_press(self, key_code: int, special: bool):
        if not self._desired_size:
            super()._key_press(key_code, special)
            return

        input_key = DOMInputKey(key_code, special)
        prev_value = self._value
        prev_cursor_position = self._cursor_position
        if input_key.is_char():
            self._value = self._value[:self._cursor_position] + \
                input_key.char() + \
                self._value[self._cursor_position:]
            self._cursor_position += 1
        elif input_key.key == input_key.KEY_BACKSPACE:
            self._value = self._value[:self._cursor_position-1] + \
                self._value[self._cursor_position:]
            self._cursor_position = max(0, self._cursor_position - 1)
        elif input_key.key == input_key.KEY_DELETE:
            self._value = self._value[:self._cursor_position] + \
                self._value[self._cursor_position + 1:]
        elif input_key.key == input_key.KEY_CLEAR_WORD_BACKWARD:
            index = self._value[:self._cursor_position].rstrip().rfind(" ")
            self._value = self._value[:index + 1] + \
                self._value[self._cursor_position:]
            self._cursor_position = index + 1
        elif input_key.key == input_key.KEY_CLEAR_LINE_FORWARD:
            self._value = self._value[:self._cursor_position]
        elif input_key.key == input_key.KEY_CLEAR_LINE:
            self._value = ""
            self._cursor_position = 0
        elif input_key.key == input_key.KEY_ARROW_LEFT:
            self._cursor_position = max(0, self._cursor_position - 1)
        elif input_key.key == input_key.KEY_ARROW_RIGHT:
            self._cursor_position = min(len(self._value), self._cursor_position + 1)
        elif input_key.key == input_key.KEY_MOVE_WORD_BACKWARD or \
                input_key.key == input_key.KEY_MOVE_WORD_BACKWARD_1:
            index = self._value[:self._cursor_position].rstrip().rfind(" ")
            self._cursor_position = max(0, index + 1)
        elif input_key.key == input_key.KEY_MOVE_WORD_FORWARD or \
                input_key.key == input_key.KEY_MOVE_WORD_FORWARD_1:
            # the goal is to find the index of a letter following a whitespace
            input = self._value[self._cursor_position:]
            offset = len(input) - len(input.lstrip())
            if offset > 0:
                # if the next character is a whitespace, move to the next non-whitespace character
                self._cursor_position = min(len(self._value), self._cursor_position + offset)
            else:
                # if the next character is not a whitespace, find the next whitespace character
                # first
                index = input.find(" ")
                if index == -1:
                    self._cursor_position = len(self._value)
                else:
                    # find the index of the next non-whitespace character after that
                    input = self._value[self._cursor_position + index:]
                    index = index + self._cursor_position + len(input) - len(input.lstrip())
                    self._cursor_position = min(len(self._value), index)
        elif input_key.key == input_key.KEY_HOME or \
                input_key.key == input_key.KEY_MOVE_LINE_FORWARD:
            self._cursor_position = 0
        elif input_key.key == input_key.KEY_END or \
                input_key.key == input_key.KEY_MOVE_LINE_BACKWARD:
            self._cursor_position = len(self._value)
        else:
            super()._key_press(key_code, special)
            return

        self._value_offset = self._calculate_offset(prev_cursor_position)
        # Force the bubbling up if there was a resize
        prev_line_count = self._get_line_count(self._desired_size, prev_value)
        next_line_count = self._get_line_count(self._desired_size, self._value)
        self._rerender(True, resize=(False, prev_line_count != next_line_count))
        super()._key_press(key_code, special)

    def _should_render(self, screen: DOMScreen, force: bool=False) -> bool:
        return super()._should_render(screen, force) or \
            self._render_value != self._value or \
            self._render_cursor_position != self._cursor_position

    def _render(self, screen: DOMScreen, force: bool = False):
        if not self._should_render(screen, force) or not self._can_display(screen):
            super()._render(screen)
            return
        if self._render_full_size is not None and self._render_full_size != self._desired_size:
            # The desired size changed because the parent is granting more/less room
            self._value_offset = self._calculate_offset(0, self._desired_size)

        # TODO: Handle a resize event that causes the cursor to be hidden
        # Each "pixel" on the screen has to be filled up
        if self._is_short_scroll():
            display_character_count = screen.width()
        else:
            display_character_count = screen.height() * screen.width()
        is_truncated_start = self._value_offset != 0

        if is_truncated_start and not self._is_short_scroll():
            # The static prefix does not affect the number of available characters since it takes
            # up a whole line
            is_truncated_end = len(self._value) - self._value_offset > display_character_count
        else:
            is_truncated_end = len(self._value) - self._value_offset > \
                display_character_count - self._get_static_prefix_size()

        self._render_static_prefix(screen)

        cursor_position = self._cursor_position - self._value_offset
        if not is_truncated_start or self._is_short_scroll():
            cursor_position += self._get_static_prefix_size()
        cursor_line_index = cursor_position // screen.width()

        for vertical_offset in range(0, screen.height()):
            is_first_line = vertical_offset == 0
            is_last_line = vertical_offset == self._desired_size[VERTICAL] - 1 or \
                (
                    self._desired_size[VERTICAL] == 2 and
                    vertical_offset == self._desired_size[VERTICAL] - 2
                )

            if not self._is_short_scroll() and is_truncated_start and is_first_line:
                self.window.screen.print_at(
                    ">...." + " " * (screen.width() - 5 - self._get_static_prefix_size()),
                    screen.position[HORIZONTAL] + self._get_static_prefix_size(),
                    screen.position[VERTICAL],
                    colour=self._computed_style.color.value if self._computed_style.color
                        else Color.WHITE.value,
                    bg=self._computed_style.background.value if self._computed_style.background
                        else Color.BLACK.value
                )
                continue

            line_index = vertical_offset - screen.offset[VERTICAL]
            value_start_index = line_index * screen.width() + self._value_offset
            if not is_truncated_start or self._is_short_scroll():
                if is_first_line:
                    value_end_index = value_start_index + screen.width() \
                        - self._get_static_prefix_size()
                else:
                    value_start_index -= self._get_static_prefix_size()
                    value_end_index = value_start_index + screen.width()
            else:
                value_end_index = value_start_index + screen.width()

            # Determine the sub-string of the input value to be printed up to the cursor.
            if line_index != cursor_line_index:
                value = self._value[value_start_index:value_end_index]
                line_value_length = len(value)
            else:
                value = self._value[value_start_index:self._cursor_position]
                line_value_length = len(self._value[value_start_index:value_end_index])
            # This can happen when there are 2 lines available for the short scroll
            if self._is_short_scroll() and not is_first_line:
                value = ""
                line_value_length = 0

            if is_first_line:
                if is_truncated_start:
                    # The value is truncated at the beginning
                    value = "<" + value[1:]
                line_value_length += self._get_static_prefix_size()

            self.window.screen.print_at(
                value,
                screen.position[HORIZONTAL] if not is_first_line
                    else screen.position[HORIZONTAL] + self._get_static_prefix_size(),
                screen.position[VERTICAL] + vertical_offset,
                colour=self._computed_style.color.value if self._computed_style.color
                    else Color.WHITE.value,
                bg=self._computed_style.background.value if self._computed_style.background
                    else Color.BLACK.value
            )
            # Render the cursor
            if line_index == cursor_line_index:
                # Setup the cursor background
                if self.focused:
                    cursor_background = Color.WHITE.value
                else:
                    cursor_background = Color.GREY_37.value

                # Pick the character under the cursor and update the value length if it's an added
                # character at the end of the line
                if self._cursor_position == len(self._value):
                    cursor_char = " "
                    line_value_length += 1
                else:
                    cursor_char = self._value[self._cursor_position]

                cursor_index = cursor_position % screen.width()
                self.window.screen.print_at(
                    cursor_char,
                    screen.position[HORIZONTAL] + cursor_index,
                    screen.position[VERTICAL] + vertical_offset,
                    bg=cursor_background
                )
                self.window.screen.print_at(
                    self._value[self._cursor_position + 1:value_end_index],
                    screen.position[HORIZONTAL] + cursor_index + 1,
                    screen.position[VERTICAL] + vertical_offset,
                    colour=self._computed_style.color.value if self._computed_style.color
                        else Color.WHITE.value,
                    bg=self._computed_style.background.value if self._computed_style.background
                        else Color.BLACK.value
                )

            if is_truncated_end and is_last_line:
                # Add the character to indicate there is more text
                if self._is_short_scroll():
                    end_char = ">"
                else:
                    end_char = "<...."

                self.window.screen.print_at(
                    end_char,
                    screen.position[HORIZONTAL] + line_value_length - len(end_char),
                    screen.position[VERTICAL] + vertical_offset,
                    colour=self._computed_style.color.value if self._computed_style.color
                        else Color.WHITE.value,
                    bg=self._computed_style.background.value if self._computed_style.background
                        else Color.BLACK.value
                )
            else:
                # Pad with spaces to get rid of lingering characters
                padding_size = screen.width() - line_value_length
                padding = " " * padding_size
                self.window.screen.print_at(
                    padding,
                    screen.position[HORIZONTAL] + line_value_length,
                    screen.position[VERTICAL] + vertical_offset,
                )

        # We'll take what we can size wise
        self._render_full_size = self._desired_size
        self._render_value = self._value
        self._render_cursor_position = self._cursor_position
        super()._render(screen)


