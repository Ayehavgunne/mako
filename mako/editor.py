import contextlib
import re
from pathlib import Path

import pyperclip
from rich.cells import get_character_cell_size
from rich.console import RenderableType
from rich.syntax import Syntax
from rich.text import Text
from rich.traceback import Traceback
from textual.app import ComposeResult
from textual.events import Click, Key, Paste
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Placeholder, Static

from mako.config import config, Language
from mako.custom_syntax import CustomSyntax
from mako.util import call_command


class Editor(Static, can_focus=True):
    BINDINGS = [
        ("left", "cursor_left", "cursor left"),
        ("right", "cursor_right", "cursor right"),
        ("up", "cursor_up", "cursor up"),
        ("down", "cursor_down", "cursor down"),
        ("backspace", "delete_left", "delete left"),
        ("home", "home", "home"),
        ("end", "end", "end"),
        ("delete", "delete_right", "delete right"),
        ("tab", "add_tab", "add a tab or tabs worth of spaces"),
        ("ctrl+s", "save_file", "save file to disk"),
        ("ctrl+c", "copy", "copy selection to system clipboard"),
        ("ctrl+v", "paste", "paste contents from system clipboard at cursor"),
    ]
    COMPONENT_CLASSES = {"editor_cursor", "editor_highlight_line"}
    DEFAULT_CSS = """
        Editor {
            background: $boost;
            color: $text;
            padding: 0 2;
            border: tall $background;
            width: 100%;
            height: 100%;
            min-height: 1;
            content-align-horizontal: center;
        }
        Editor:focus {
            border: tall $accent;
        }
        Editor > .editor_cursor {
            background: $surface;
            color: $text;
            text-style: reverse;
        }
        Editor > .editor_highlight_line {
            background: $boost-darken-2;
        }
        Editor > #left_gutter {
            width: 1;
        }
    """

    cursor_blink: bool = reactive(default=True)
    _top_offset: int = reactive(default=0)
    _left_offset: int = reactive(default=0)
    value: str = reactive(default="", layout=True, init=False)
    file_path: Path = reactive(default=None, layout=True, init=False)
    cursor_column: int = reactive(default=0)
    cursor_line: int = reactive(default=1)
    _cursor_visible: bool = reactive(default=True)

    class ValueChanged(Message, bubble=True):
        def __init__(self, sender: "Editor", value: str) -> None:
            super().__init__()
            self.value = value
            self.editor = sender

    class CursorLineChanged(Message, bubble=True):
        def __init__(self, sender: "Editor", value: int) -> None:
            super().__init__()
            self.value = value
            self.editor = sender

    class CursorColumnChanged(Message, bubble=True):
        def __init__(self, sender: "Editor", value: int) -> None:
            super().__init__()
            self.value = value
            self.editor = sender

    class FileChanged(Message, bubble=True):
        def __init__(self, sender: "Editor", value: Path | str) -> None:
            super().__init__()
            self.value = value
            self.editor = sender

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
        self.change_lines = []
        self.language_config: Language = Language()

    def compose(self) -> ComposeResult:
        yield Placeholder(id="left_gutter")
        yield Placeholder(id="right_gutter")

    @property
    def _cursor_at_end(self) -> bool:
        return self.cursor_column >= len(self.value)

    @property
    def top_offset(self) -> int:
        return self._top_offset

    @top_offset.setter
    def top_offset(self, offset: int) -> None:
        if offset >= 0:
            self._top_offset = offset

    @property
    def left_offset(self) -> int:
        return self._left_offset

    @left_offset.setter
    def left_offset(self, offset: int) -> None:
        if offset <= 0:
            offset = 0
        self._left_offset = offset

    async def watch_file_path(self, value: Path) -> None:
        if self.styles.auto_dimensions:
            self.refresh(layout=True)
        self.value = value.read_text()
        self.change_lines = self.app.git_working_changes[value.as_posix()]
        self.language_config = config.get_language(self.file_path.parts[-1])
        self.cursor_line = 1
        self.cursor_column = 0
        self.post_message(self.FileChanged(self, value))

    async def watch_value(self, value: str) -> None:
        if self.styles.auto_dimensions:
            self.refresh(layout=True)
        self.post_message(self.ValueChanged(self, value))

    async def watch_cursor_line(self, value: int) -> None:
        self.post_message(self.CursorLineChanged(self, value))
        if self.cursor_column > len(self.current_line):
            value = len(self.current_line)
        else:
            value = self.cursor_column
        self.post_message(self.CursorColumnChanged(self, value))

    async def watch_cursor_column(self, value: int) -> None:
        if value > len(self.current_line):
            value = len(self.current_line) - 1
        self.post_message(self.CursorColumnChanged(self, value))

    def render(self) -> RenderableType:
        if not self.value and self.file_path:
            self.value = self.file_path.read_text()
        if self.file_path is not None:
            try:
                syntax = CustomSyntax(
                    self.value,
                    lexer=self.file_path.parts[-1].split(".")[-1],
                    line_numbers=self.language_config.line_numbers,
                    word_wrap=self.language_config.word_wrap,
                    indent_guides=self.language_config.indent_guides,
                    line_range=(
                        self.top_offset + 1,
                        self.top_offset + self.container_viewport.height + 1,
                    ),
                    column_offset=self.left_offset,
                    code_width=self.language_config.column_width,
                    tab_size=self.language_config.tab_size,
                )
            except Exception:  # noqa
                return Traceback(width=None)
            self.stylize_line(syntax)
            self.stylize_cursor(syntax)
            return syntax
        return self._value

    def stylize_cursor(self, syntax: Syntax) -> None:
        if self._cursor_visible and self.has_focus:
            cursor_style = self.get_component_rich_style("editor_cursor")
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

    def stylize_line(self, syntax: Syntax) -> None:
        if config.highlight_line:
            line_style = self.get_component_rich_style("editor_highlight_line")
            syntax.stylize_range(
                line_style,
                (self.cursor_line, 0),
                (self.cursor_line, len(self.current_line)),
            )

    @property
    def _value(self) -> Text:
        if not self.value and self.file_path:
            self.value = self.file_path.read_text()
        return Text(self.value, no_wrap=True, overflow="ignore")

    @property
    def current_line(self) -> str:
        try:
            return self.value.split("\n")[self.cursor_line - 1]
        except IndexError:
            return ""

    @property
    def next_line(self) -> str:
        try:
            return self.value.split("\n")[self.cursor_line]
        except IndexError:
            return ""

    def get_indent_level(self, line: int) -> int:
        line = self.value.split("\n")[line - 1]
        spaces = 0
        tabs = False
        for char in line:
            if char in "\t":
                spaces += 1
                tabs = True
            elif char == " ":
                spaces += 1
            else:
                break
        if not tabs:
            spaces //= self.language_config.tab_size
        return spaces

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
        if self.cursor_blink:
            self.blink_timer.resume()

    async def on_key(self, event: Key) -> None:
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

    def on_paste(self, event: Paste) -> None:
        self.insert_text_at_cursor(event.text)
        event.stop()

    def on_click(self, event: Click) -> None:
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
        lines = self.value.split("\n")
        try:
            line = lines[self.cursor_line - 1]
        except IndexError:
            line = ""
        if self.cursor_column > len(line):
            lines.insert(self.cursor_line, "")
        else:
            value = line
            line = value[: self.cursor_column]
            after = value[self.cursor_column :]
            lines.insert(self.cursor_line, after)
        lines[self.cursor_line - 1] = line
        self.cursor_line += 1
        if self.language_config.auto_indent:
            indent_level = self.get_indent_level(self.cursor_line)
            self.cursor_column = indent_level * self.language_config.tab_size
            lines[self.cursor_line - 1] = (
                f"{' ' * self.cursor_column}{lines[self.cursor_line - 1]}"
            )
        else:
            self.cursor_column = 0
        self.value = "\n".join(lines)

    def insert_text_at_cursor(self, text: str) -> None:
        lines = self.value.split("\n")
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
        if self.cursor_column <= self.left_offset:
            self.left_offset -= 1

    def action_cursor_right(self) -> None:
        if self.cursor_column < len(self.current_line):
            self.cursor_column += 1
        if self.cursor_column >= self.language_config.column_width + self.left_offset:
            self.left_offset += 1

    def action_cursor_up(self) -> None:
        if self.cursor_line > 1:
            self.cursor_line -= 1
        if self.cursor_line <= self.top_offset:
            self.top_offset -= 1
        if self.cursor_column >= len(self.current_line):
            self.left_offset = (
                len(self.current_line) - self.language_config.column_width
            )
        if self.cursor_column < len(self.current_line):
            self.left_offset = self.cursor_column - self.language_config.column_width

    def action_cursor_down(self) -> None:
        if self.cursor_line < len(self.value.split("\n")):
            self.cursor_line += 1
        if self.cursor_line >= self.container_viewport.height + self.top_offset - 1:
            self.top_offset += 1
        if self.cursor_column >= len(self.current_line):
            self.left_offset = (
                len(self.current_line) - self.language_config.column_width
            )
        if self.cursor_column < len(self.current_line):
            self.left_offset = self.cursor_column - self.language_config.column_width

    def action_home(self) -> None:
        self.cursor_column = 0
        self.left_offset = 0

    def action_end(self) -> None:
        self.cursor_column = len(self.current_line)
        self.left_offset = len(self.current_line) - self.language_config.column_width

    def action_add_tab(self) -> None:
        remainder = self.cursor_column % self.language_config.tab_size
        if remainder == 0:
            self.insert_text_at_cursor(" " * self.language_config.tab_size)
        else:
            self.insert_text_at_cursor(
                " " * (self.language_config.tab_size - remainder),
            )

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
        lines = self.value.split("\n")
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
        lines = self.value.split("\n")
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

        if self.file_path:
            with self.file_path.open("w") as file_handler:
                file_handler.write(self.value)

    def action_copy(self) -> None:
        pyperclip.copy(self.value)

    def action_paste(self) -> None:
        self.insert_text_at_cursor(pyperclip.paste())

    def action_format_document(self) -> None:
        if self.file_path:
            formatter = self.language_config.formatter
            command = [formatter.command, *formatter.args]
            out, error = call_command(command, self.value)
            self.value = out
