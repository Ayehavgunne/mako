from pathlib import Path

from rich.console import RenderableType
from textual.app import ComposeResult
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Label, Static

from mako.editor import Editor


class CursorPosition(Label):
    line: int = reactive(default=0)
    column: int = reactive(default=0)

    def render(self) -> RenderableType:
        return f"{self.line}:{self.column}"


class Footer(Static):
    DEFAULT_CSS = """
        Footer {
            background: #2e2e2e;
            color: $text;
            dock: bottom;
            height: 1;
            layout: grid;
            grid-size: 3;
            grid-columns: 1fr 1fr 1fr;
        }
        Footer > #left {
            text-style: bold;
            width: 100%;
        }
        Footer > #middle {
            text-style: bold;
            text-align: center;
            width: 100%;
        }
        Footer > #right {
            text-style: bold;
            text-align: right;
            width: 100%;
        }
        Footer > #cursor_position {
            offset-y: 90;
        }
        """

    def compose(self) -> ComposeResult:
        yield Label(id="left")
        yield Label(id="middle")
        with Label(id="right"):
            yield CursorPosition(id="cursor_position")

    def update_text(self, message: Message) -> None:
        match message:
            case Editor.FileChanged() as file_change:
                self.update_middle(file_path=file_change.value)
            case Editor.CursorLineChanged() as line_change:
                self.update_right(line=line_change.value)
            case Editor.CursorColumnChanged() as line_change:
                self.update_right(column=line_change.value)

    def update_left(self) -> None:
        self.get_child_by_id("left")

    def update_middle(self, file_path: Path) -> None:
        middle = self.get_child_by_id("middle")
        middle.update(file_path.as_posix())

    def update_right(self, line: int | None = None, column: int | None = None) -> None:
        cursor_position = self.get_child_by_id("right").get_child_by_id(
            "cursor_position",
        )
        if line is not None:
            cursor_position.line = line
        if column is not None:
            cursor_position.column = column + 1