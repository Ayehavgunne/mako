from pathlib import Path

from rich.console import RenderableType
from textual.app import ComposeResult
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Label, Static

from mako.editor import Editor
from mako.util import call_command


class CursorPosition(Label):
    line: int = reactive(default=0)
    column: int = reactive(default=0)

    def render(self) -> RenderableType:
        return f"{self.line}:{self.column}"


class Footer(Static):
    def compose(self) -> ComposeResult:
        yield Label(id="left")
        yield Label(id="middle")
        yield CursorPosition(id="right")

    def on_mount(self) -> None:
        self.update_left()

    def update_text(self, message: Message) -> None:
        match message:
            case Editor.FileChanged() as file_change:
                self.update_middle(file_path=file_change.value)
            case Editor.CursorLineChanged() as line_change:
                self.update_right(line=line_change.value)
            case Editor.CursorColumnChanged() as line_change:
                self.update_right(column=line_change.value)

    def update_left(self) -> None:
        left = self.get_child_by_id("left")
        cmd = "git branch --show-current".split(" ")
        out, _ = call_command(cmd)
        left.update(out)

    def update_middle(self, file_path: Path | str) -> None:
        middle = self.get_child_by_id("middle")
        if isinstance(file_path, Path):
            middle.update(file_path.as_posix())
        else:
            middle.update(file_path)

    def update_right(self, line: int | None = None, column: int | None = None) -> None:
        cursor_position = self.get_child_by_id("right")
        if line is not None:
            cursor_position.line = line
        if column is not None:
            cursor_position.column = column + 1
