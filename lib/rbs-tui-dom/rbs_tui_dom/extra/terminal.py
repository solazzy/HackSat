import asyncio
import logging
import os
import pty
import signal
import sys
from abc import ABC, abstractmethod
from asyncio import StreamReader
from asyncio.subprocess import Process
from pathlib import Path
from typing import Set, List, Optional

from rbs_tui_dom.dom import DOMScreen, DOMStyle, HORIZONTAL, VERTICAL, Color, DOMInputKey, \
    DOMKeyboardEvent, DOMSize, DOMResizeEvent, DOMEvent
from rbs_tui_dom.dom.layout import DOMStackLayout
from rbs_tui_dom.dom.style import Scroll
from rbs_tui_dom.dom.text import DOMTextInput, DOMTextFlex
from rbs_tui_dom.dom.types import FULL_WIDTH, GROW_HEIGHT


class DOMShellInput(DOMTextInput):
    def __init__(
            self,
            cwd: str,
            id: str = None,
            classnames: Set[str] = None,
            style: DOMStyle = DOMStyle(),
    ):
        super().__init__(id, classnames, style)
        self._dirname = os.path.basename(cwd)
        self._static_prefix_length = 2 + len(self._dirname) + 1
        self._task_mode = False
        self._task_prefix = ""

    def enable_task_mode(self, render: bool = True):
        if self._task_mode is True:
            return
        self._task_mode = True
        self.set_task_prefix("", render)

    def disable_task_mode(self, render: bool = True):
        if self._task_mode is False:
            return
        self._task_mode = False
        self.set_task_prefix("", render)

    def set_task_prefix(self, prefix: str, render: bool = True):
        self._task_prefix = prefix
        self._value_offset = self._calculate_offset(self._cursor_position)
        if render:
            self._rerender()

    def set_cwd(self, cwd: str, render: bool = True):
        self._dirname = os.path.basename(cwd)
        self._static_prefix_length = 2 + len(self._dirname) + 1
        self._value_offset = self._calculate_offset(self._cursor_position)
        if render:
            self._rerender()

    def get_task_value(self) -> str:
        return self._task_prefix + self.get_value()

    def _get_static_prefix_size(self) -> int:
        return self._static_prefix_length if not self._task_mode else len(self._task_prefix)

    def _calculate_desired_size(self, max_size: DOMSize) -> DOMSize:
        desired_height = (len(self._value) + self._static_prefix_length) // max_size[HORIZONTAL] + 1
        if desired_height == 2:
            desired_height = 3
        max_height = max_size[VERTICAL]
        if max_height == 2:
            max_height = 1
        self._desired_size = self._calculate_styled_size(
            (max_size[HORIZONTAL], min(desired_height, max_height))
        )
        return self._desired_size

    def _render_static_prefix(self, screen: DOMScreen):
        if self._task_mode:
            # TODO: This won't wrap
            self.window.screen.print_at(
                self._task_prefix,
                screen.position[HORIZONTAL],
                screen.position[VERTICAL],
                colour=self._computed_style.color.value if self._computed_style.color
                    else Color.WHITE.value,
                bg=self._computed_style.background.value if self._computed_style.background
                    else Color.BLACK.value
            )
            return

        self.window.screen.print_at(
            f"➜ ",
            screen.position[HORIZONTAL],
            screen.position[VERTICAL],
            colour=Color.GREEN_1.value
        )
        self.window.screen.print_at(
            f"{self._dirname} ",
            screen.position[HORIZONTAL] + 2,
            screen.position[VERTICAL],
            colour=Color.CYAN_1.value
        )


class DOMShellLogItem(DOMTextFlex):
    def __init__(
            self,
            value: str = "",
            style: DOMStyle = DOMStyle(),
            terminated: bool = False
    ):
        super().__init__(value, style=style)
        # Indicate that the log item is terminated with a new line
        self.terminated = terminated


class DOMShellLogCommand(DOMShellLogItem):
    def __init__(self, cwd: str, value: str):
        super().__init__(
            value,
            style=DOMStyle(size=(FULL_WIDTH, GROW_HEIGHT)),
            terminated=True,
        )
        self._dirname = os.path.basename(cwd)
        self._static_prefix_length = 3 + len(self._dirname)

    def _render_static_prefix(self, screen: DOMScreen):
        self.window.screen.print_at(
            f"➜ ",
            screen.position[HORIZONTAL],
            screen.position[VERTICAL],
            colour=Color.GREEN_1.value
        )
        self.window.screen.print_at(
            f"{self._dirname} ",
            screen.position[HORIZONTAL] + 2,
            screen.position[VERTICAL],
            colour=Color.CYAN_1.value
        )


class DOMShellLog(DOMStackLayout):
    pass


class DOMShellStdout:
    def __init__(self, dom_shell: 'DOMShell'):
        self._dom_shell = dom_shell

    def _create_dom(self, value: str, terminated: bool):
        return DOMShellLogItem(value, terminated=terminated)

    def write(self, value: str):
        if self._dom_shell._output_log._children:
            dom_prev_log_element = self._dom_shell._output_log._children[-1]
        else:
            dom_prev_log_element = None

        if value[0] != "\n" and isinstance(dom_prev_log_element, DOMShellLogItem) and \
                not dom_prev_log_element.terminated:
            # Add the line (up to the first new line) to the previous element but only if it's a
            #  log item
            separator_index = value.find("\n")
            if separator_index != -1:
                append_value = value[:separator_index]
                value = value[separator_index + 1:]
            else:
                append_value = value
                value = ""
            dom_prev_log_element.set_value(dom_prev_log_element.get_value() + append_value)
        if value and value[-1] != "\n":
            # Add the end of the line (up to the last new line) to the input element's prefix
            separator_index = value.rfind("\n")
            if separator_index != -1:
                prepend_value = value[separator_index + 1:]
                value = value[:separator_index]
            else:
                prepend_value = value
                value = ""
            self._dom_shell._input.set_task_prefix(prepend_value)
            terminated = False
        else:
            terminated = True

        if value:
            lines = value.split("\n")
            children = []
            for i, line in enumerate(lines):
                if not line:
                    continue
                # If the line is not terminated, following writes may append to it
                line_terminated = i != len(lines) - 1 or terminated
                children.append(self._create_dom(line, line_terminated))
            self._dom_shell._output_log.add_children(children)

        self._dom_shell.move_min(VERTICAL)

    def _write_buffer(self, buffer: List[bytes]):
        if not buffer:
            return
        value = b"".join(buffer).decode("utf-8")
        self.write(value)

    async def pipe(self, reader: StreamReader):
        buffer = []
        while True:
            try:
                value = await asyncio.wait_for(reader.read(1), 0.1)
                if not value:
                    # The stream has ended, write out the buffer if it contains anything
                    self._write_buffer(buffer)
                    break
                buffer.append(value)
                if len(buffer) >= 1000:
                    self._write_buffer(buffer)
                    buffer.clear()
            except asyncio.TimeoutError:
                self._write_buffer(buffer)
                buffer.clear()


class DOMShellStderr(DOMShellStdout):
    pass


class ShellTask(ABC):
    @abstractmethod
    def run(self):
        raise NotImplementedError()

    @abstractmethod
    def write(self, data: str):
        raise NotImplementedError()

    @abstractmethod
    def terminate(self):
        raise NotImplementedError()


class SubprocessShellTask(ShellTask):
    def __init__(
        self,
        command: str,
        cwd: str,
        stdout: DOMShellStdout,
        stderr: DOMShellStderr,
    ):
        self._command = command
        self._cwd = cwd
        self._stdout = stdout
        self._stderr = stderr
        self._process: Optional[Process] = None
        self._process_stdin_fd: Optional[int] = None

    async def run(self):
        master, slave = pty.openpty()
        self._process = await asyncio.create_subprocess_shell(
            self._command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            stdin=slave,
            close_fds=True,
            preexec_fn=os.setpgrp,
            cwd=self._cwd
        )
        os.close(slave)
        self._process_stdin_fd = master
        await asyncio.gather(
            self._stdout.pipe(self._process.stdout),
            self._stderr.pipe(self._process.stderr),
            self._process.wait(),
        )
        os.close(master)

    def write(self, data: str):
        if self._process.returncode is None:
            os.write(self._process_stdin_fd, data.encode("utf-8"))

    def terminate(self):
        if self._process.returncode is None:
            self._process.terminate()


class DOMShell(DOMStackLayout):
    def __init__(
            self,
            id: str = None,
            classnames: Set[str] = None,
            style: DOMStyle = DOMStyle(),
    ):
        self._cwd = os.path.abspath(os.getcwd())
        self._prev_cwd = self._cwd
        self._history = [""]
        self._history_position = 0
        self._dom_stdout = DOMShellStdout(self)
        self._dom_stderr = DOMShellStderr(self)
        self._active_task: Optional[SubprocessShellTask] = None
        self._sigint_handler = None

        self._output_log = DOMShellLog(
            id=f"{id}.log" if id else None,
            style=DOMStyle(size=(FULL_WIDTH, GROW_HEIGHT))
        )
        self._input = DOMShellInput(
            self._cwd,
            id=f"{id}.input" if id else None,
        )
        super().__init__(
            id=id,
            classnames=classnames,
            orientation=VERTICAL,
            style=DOMStyle.merge(style, DOMStyle(scroll=Scroll.LINE)),
            children=[
                # Push everythign down
                self._output_log,
                self._input
            ]
        )

    async def _run_command(
            self,
            command: str,
    ):
        clean_command = command.strip()
        if clean_command.startswith("cd"):
            dir_path = clean_command.replace("\"", "").replace("\\", "")[2:].strip()
            if dir_path == "-":
                dir_path = self._prev_cwd
            elif dir_path.startswith("~"):
                dir_path = str(Path.home()) + dir_path[1:]
            else:
                dir_path = os.path.abspath(os.path.join(self._cwd, dir_path))
            if not os.path.isdir(dir_path):
                self._dom_stdout.write(f"cd: no such file or directory: {dir_path}\n")
            else:
                self._prev_cwd = self._cwd
                self._cwd = dir_path
                self._input.set_cwd(dir_path, render=False)
        elif clean_command.startswith("exit") or clean_command.startswith("quit"):
            sys.exit(0)
        else:
            self._active_task = SubprocessShellTask(
                command,
                self._cwd,
                self._dom_stdout,
                self._dom_stderr
            )
            await self._active_task.run()
        self._active_task = None
        self._input.set_value("", render=False)
        self._input.disable_task_mode(render=True)
        self.move_min(VERTICAL)

    def focus(self):
        self._input.focus()

    def _on_focus(self, event: DOMEvent):
        self._sigint_handler = signal.getsignal(signal.SIGINT)
        signal.signal(signal.SIGINT, self._on_sigint)

    def _on_blur(self, event: DOMEvent):
        signal.signal(signal.SIGINT, self._sigint_handler)
        self._sigint_handler = None

    def _on_sigint(self, *args):
        if self._active_task:
            self._output_log.add_child(
                DOMShellLogItem(self._input.get_task_value(), terminated=True)
            )
            self._active_task.terminate()
        else:
            self._output_log.add_child(
                DOMShellLogCommand(self._cwd, "Use `exit` to close the application")
            )
        self._input.set_value("", render=False)
        self.move_min(VERTICAL)

    def _on_child_resize(self, event: DOMResizeEvent):
        if event.target != self._input:
            super()._on_child_resize(event)
            return
        self._rerender(resize=event.resize_axis, refresh_screen=False)
        self.move_min(VERTICAL)
        self.window.screen.refresh()

    def _on_run_command(self, command: str):
        self._history[self._history_position] = command
        self._history.append("")
        self._history_position = len(self._history) - 1
        asyncio.ensure_future(self._run_command(command))

        self._output_log.add_child(DOMShellLogCommand(self._cwd, command))
        self._input.enable_task_mode(render=False)
        self._input.set_value("", render=True)
        self.move_min(VERTICAL)

    def _on_task_input(self, input: str):
        self._output_log.add_child(
            DOMShellLogItem(self._input.get_task_value(), terminated=True)
        )
        self._input.set_task_prefix("", render=False)
        self._input.set_value(render=True)
        self._active_task.write(input + "\n")
        self.move_min(VERTICAL)

    def _on_history_position_update(self, position: int) -> bool:
        if position == self._history_position:
            self.logger.debug("the history position is not changing")
            return False
        self._history_position = position
        self._input.set_value(self._history[self._history_position], render=True)
        self.move_min(VERTICAL)

    def _on_keyboard_event(self, keyboard_event: DOMKeyboardEvent):
        # The keyboard event should not ever need to bubble further up the DOM tree
        keyboard_event.stop_propagation = True
        if keyboard_event.key_code == DOMInputKey.KEY_ENTER:
            if self._active_task is None:
                self._on_run_command(self._input.get_value())
            else:
                self._on_task_input(self._input.get_value())
        elif keyboard_event.key_code == DOMInputKey.KEY_PAGE_UP or \
                keyboard_event.key_code == DOMInputKey.KEY_PAGE_DOWN:
            # Let the normal scroll happen
            super()._on_keyboard_event(keyboard_event)
        elif self._active_task is None:
            if keyboard_event.key_code == DOMInputKey.KEY_ARROW_UP:
                self._on_history_position_update(max(0, self._history_position - 1))
            elif keyboard_event.key_code == DOMInputKey.KEY_ARROW_DOWN:
                self._on_history_position_update(
                    min(len(self._history) - 1, self._history_position + 1)
                )
            else:
                # Reset the history position since the current command is now the latest command
                self._history_position = len(self._history) - 1
                self._history[self._history_position] = self._input.get_value()
                # The input received some new value, make sure it's visible
                self.move_min(VERTICAL)
        else:
            self.move_min(VERTICAL)


