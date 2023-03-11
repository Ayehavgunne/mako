import contextlib
import re
from pathlib import Path
from typing import ClassVar, TYPE_CHECKING

import pyperclip
from rich.cells import cell_len, get_character_cell_size
from rich.syntax import Syntax
from rich.text import Text
from rich.traceback import Traceback
from textual.binding import Binding, BindingType
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Static

from mako.config import config
from mako.formatter import format_doc
from mako.logger import mako_logger

if TYPE_CHECKING:
    from rich.console import RenderableType
    from textual.events import Click, Key, Paste


class Editor(Static, can_focus=True):
    """A text editor widget."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("left", "cursor_left", "cursor left", show=False),
        Binding("right", "cursor_right", "cursor right", show=False),
        Binding("up", "cursor_up", "cursor up", show=False),
        Binding("down", "cursor_down", "cursor down", show=False),
        Binding("backspace", "delete_left", "delete left", show=False),
        Binding("home", "home", "home", show=False),
        Binding("end", "end", "end", show=False),
        Binding("delete", "delete_right", "delete right", show=False),
        Binding("ctrl+s", "save_file", "save file to disk", show=False),
        Binding("ctrl+c", "copy", "copy selection to system clipboard", show=False),
        Binding(
            "ctrl+v",
            "paste",
            "paste contents from system clipboard at cursor",
            show=False,
        ),
    ]
    COMPONENT_CLASSES: ClassVar[set[str]] = {"editor--cursor"}
    DEFAULT_CSS = """
    Editor {
        background: $boost;
        color: $text;
        padding: 0 2;
        border: tall $background;
        width: 100%;
        height: 1;
        min-height: 1;
    }
    Editor:focus {
        border: tall $accent;
    }
    Editor>.editor--cursor {
        background: $surface;
        color: $text;
        text-style: reverse;
    }
    """

    cursor_blink = reactive(default=True)
    top_offset = reactive(default=0)
    value = reactive(default="", layout=True, init=False)
    file_path = reactive(default=None, layout=True, init=False)
    editor_scroll_offset = reactive(default=0)
    cursor_column = reactive(default=0)
    cursor_line = reactive(default=1)
    view_position = reactive(default=0)
    complete = reactive(default="")
    width = reactive(default=1)
    _cursor_visible = reactive(default=True)

    class Changed(Message, bubble=True):
        def __init__(self, sender: "Editor", value: str) -> None:
            super().__init__()
            self.value: str = value
            self.editor: Editor = sender

    def __init__(
        self,
        file_path: Path | None = None,
        name: str | None = None,
        id: str | None = None,  # noqa
        classes: str | None = None,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes, disabled=False)
        if file_path is not None:
            with contextlib.suppress(UnicodeDecodeError):
                self.value = file_path.read_text()
        self.file_path = file_path
        self.blink_timer = None

    def _position_to_cell(self, position: int) -> int:
        return cell_len(self.value[:position])

    @property
    def _cursor_offset(self) -> int:
        offset = self._position_to_cell(self.cursor_column)
        if self._cursor_at_end:
            offset += 1
        return offset

    @property
    def _cursor_at_end(self) -> bool:
        return self.cursor_column >= len(self.value)

    # def _on_focus(self) -> None:
    #     mako_logger.debug("I AM FOCUSED")
    #
    # def _on_blur(self) -> None:
    #     mako_logger.debug("I LOST FOCUS")

    def validate_cursor_position(self, cursor_position: int) -> int:
        return min(max(0, cursor_position), len(self.value))

    def validate_view_position(self, view_position: int) -> int:
        width = self.content_size.width
        return max(0, min(view_position, self.cursor_width - width))

    def watch_cursor_position(self, _: int) -> None:
        width = self.content_size.width
        if width == 0:
            self.view_position = 0
            return

        view_start = self.view_position
        view_end = view_start + width
        cursor_offset = self._cursor_offset

        if cursor_offset >= view_end or cursor_offset < view_start:
            view_position = cursor_offset - width // 2
            self.view_position = view_position
        else:
            self.view_position = self.view_position

    async def watch_file_path(self, value: str) -> None:
        if self.styles.auto_dimensions:
            self.refresh(layout=True)
        mako_logger.debug(f"loaded file {self.file_path.as_posix()}")  # noqa: G004
        self.value = self.file_path.read_text()
        self.cursor_line = 1
        self.cursor_column = 0
        self.post_message(self.Changed(self, value))

    async def watch_value(self, value: str) -> None:
        if self.styles.auto_dimensions:
            self.refresh(layout=True)
        self.post_message(self.Changed(self, value))

    @property
    def cursor_width(self) -> int:
        return self._position_to_cell(len(self.value)) + 1

    def render(self) -> "RenderableType":
        # I don't know why assign this to itself, it was just in the textual examples
        self.view_position = self.view_position

        if not self.value and self.file_path:
            self.value = self.file_path.read_text()
        if self.file_path is not None:
            try:
                syntax = Syntax(
                    self.value,
                    lexer=self.file_path.parts[-1].split(".")[-1],
                    line_numbers=True,
                    word_wrap=False,
                    indent_guides=True,
                    line_range=(
                        self.top_offset + 1,
                        self.top_offset + self.container_viewport.height + 1,
                    ),
                    code_width=config.languages[
                        Syntax.guess_lexer(self.file_path.parts[-1])
                    ].column_width,
                )
            except Exception:  # noqa
                return Traceback(width=None)
            if self._cursor_visible and self.has_focus:
                cursor_style = self.get_component_rich_style("editor--cursor")
                cursor_column = (
                    self.cursor_column
                    if self.cursor_column < len(self.current_line)
                    else len(self.current_line) - 1
                )
                syntax.stylize_range(
                    cursor_style,
                    (self.cursor_line, cursor_column),
                    (self.cursor_line, cursor_column + 1),
                )
            return syntax
        return self._value

    @property
    def _value(self) -> "Text":
        if not self.value and self.file_path:
            self.value = self.file_path.read_text()
        return Text(self.value, no_wrap=True, overflow="ignore")

    @property
    def current_line(self) -> str:
        try:
            return self.value.splitlines()[self.cursor_line - 1]
        except IndexError:
            return ""

    def _toggle_cursor(self) -> None:
        self._cursor_visible = not self._cursor_visible

    def on_mount(self) -> None:
        self.blink_timer = self.set_interval(
            0.5,
            self._toggle_cursor,
            pause=not (self.cursor_blink and self.has_focus),
        )

    def on_blur(self) -> None:
        self.blink_timer.pause()

    def on_focus(self) -> None:
        self.cursor_column = len(self.value)
        if self.cursor_blink:
            self.blink_timer.resume()

    async def on_key(self, event: "Key") -> None:
        self._cursor_visible = True
        if self.cursor_blink:
            self.blink_timer.reset()

        if await self.handle_key(event):
            event.prevent_default()
            event.stop()
            return
        if event.key == "enter":
            event.stop()
            self.insert_return_char()
            event.prevent_default()
        if event.is_printable:
            event.stop()
            if event.character is None:
                raise ValueError
            self.insert_text_at_cursor(event.character)
            event.prevent_default()

    def on_paste(self, event: "Paste") -> None:
        self.insert_text_at_cursor(event.text)
        event.stop()

    def on_click(self, event: "Click") -> None:
        offset = event.get_content_offset(self)
        if offset is None:
            return
        event.stop()
        click_x = offset.x + self.view_position
        cell_offset = 0
        _cell_size = get_character_cell_size
        for index, char in enumerate(self.value):
            if cell_offset >= click_x:
                self.cursor_column = index
                break
            cell_offset += _cell_size(char)
        else:
            self.cursor_column = len(self.value)

    def insert_return_char(self) -> None:
        lines = self.value.splitlines()
        line = lines[self.cursor_line - 1]
        if self.cursor_column > len(line):
            lines.insert(self.cursor_line, "")
        else:
            value = line
            line = value[: self.cursor_column]
            after = value[self.cursor_column :]
            lines.insert(self.cursor_line, after)
        lines[self.cursor_line - 1] = line
        self.cursor_line += 1
        self.cursor_column = 0
        self.value = "\n".join(lines)

    def insert_text_at_cursor(self, text: str) -> None:
        lines = self.value.splitlines()
        line = lines[self.cursor_line - 1]
        if self.cursor_column > len(line):
            line += text
            self.cursor_column = len(line)
        else:
            value = line
            before = value[: self.cursor_column]
            after = value[self.cursor_column :]
            line = f"{before}{text}{after}"
            self.cursor_column += len(text)
        lines[self.cursor_line - 1] = line
        self.value = "\n".join(lines)

    def action_cursor_left(self) -> None:
        if self.cursor_column > 0:
            self.cursor_column -= 1

    def action_cursor_right(self) -> None:
        if self.cursor_column < len(self.current_line):
            self.cursor_column += 1

    def action_cursor_up(self) -> None:
        if self.cursor_line > 1:
            self.cursor_line -= 1
        if self.cursor_line <= self.top_offset:
            self.top_offset -= 1

    def action_cursor_down(self) -> None:
        if self.cursor_line < len(self.value.splitlines()):
            self.cursor_line += 1
        if self.cursor_line >= self.container_viewport.height + self.top_offset - 1:
            self.top_offset += 1

    def action_home(self) -> None:
        self.cursor_column = 0

    def action_end(self) -> None:
        self.cursor_column = len(self.current_line)

    _WORD_START = re.compile(r"(?<=\W)\w")

    def action_cursor_left_word(self) -> None:
        try:
            *_, hit = re.finditer(self._WORD_START, self.value[: self.cursor_column])
        except ValueError:
            self.cursor_column = 0
        else:
            self.cursor_column = hit.start()

    def action_cursor_right_word(self) -> None:
        hit = re.search(self._WORD_START, self.value[self.cursor_column :])
        if hit is None:
            self.cursor_column = len(self.value)
        else:
            self.cursor_column += hit.start()

    def action_delete_right(self) -> None:
        lines = self.value.splitlines()
        value = lines[self.cursor_line - 1]
        delete_position = self.cursor_column
        before = value[:delete_position]
        after = value[delete_position + 1 :]
        value = f"{before}{after}"
        lines[self.cursor_line - 1] = value
        self.value = "\n".join(lines)
        self.cursor_column = delete_position

    def action_delete_right_word(self) -> None:
        after = self.value[self.cursor_column :]
        hit = re.search(self._WORD_START, after)
        if hit is None:
            self.value = self.value[: self.cursor_column]
        else:
            self.value = f"{self.value[: self.cursor_column]}{after[hit.end() - 1:]}"

    def action_delete_right_all(self) -> None:
        self.value = self.value[: self.cursor_column]

    def action_delete_left(self) -> None:
        lines = self.value.splitlines()
        line = lines[self.cursor_line - 1]
        if self.cursor_column <= 0:
            previous_line = lines[self.cursor_line - 2]
            lines[self.cursor_line - 2] = f"{previous_line}{self.current_line}"
            lines.pop(self.cursor_line - 1)
            self.cursor_line -= 1
            self.cursor_column = len(previous_line)
        elif self.cursor_column == len(line):
            line = line[:-1]
            self.cursor_column = len(line)
            lines[self.cursor_line - 1] = line
        else:
            value = line
            delete_position = self.cursor_column - 1
            before = value[:delete_position]
            after = value[delete_position + 1 :]
            line = f"{before}{after}"
            self.cursor_column = delete_position
            lines[self.cursor_line - 1] = line
        self.value = "\n".join(lines)

    def action_delete_left_word(self) -> None:
        if self.cursor_column <= 0:
            return
        after = self.value[self.cursor_column :]
        try:
            *_, hit = re.finditer(self._WORD_START, self.value[: self.cursor_column])
        except ValueError:
            self.cursor_column = 0
        else:
            self.cursor_column = hit.start()
        self.value = f"{self.value[: self.cursor_column]}{after}"

    def action_delete_left_all(self) -> None:
        if self.cursor_column > 0:
            self.value = self.value[self.cursor_column :]
            self.cursor_column = 0

    def action_save_file(self) -> None:
        if config.format_on_save:
            self.action_format_document()

        with self.file_path.open("w") as file_handler:
            file_handler.write(self.value)

    def action_copy(self) -> None:
        pyperclip.copy(self.value)

    def action_paste(self) -> None:
        self.insert_text_at_cursor(pyperclip.paste())

    def action_format_document(self) -> None:
        if self.file_path:
            self.value = format_doc(
                self.value,
                config.current_language(self.file_path.parts[-1]).formatter,
            )
