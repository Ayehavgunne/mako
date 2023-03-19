import contextlib
from pathlib import Path

from rich.console import RenderableType
from rich.syntax import Syntax
from rich.text import Text
from textual.app import ComposeResult
from textual.events import Key
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Static

from mako.util import assign_keybinds, fuzzy_finder


class FuzzyFinder(Static, can_focus=True):
    COMPONENT_CLASSES = ["selected_file", "placeholder"]
    # BINDINGS = [
    #     ("up", "move_up_a_file", "move file selector up one in the list"),
    #     ("down", "move_down_a_file", "move file selector down one in the list"),
    #     ("enter", "select_a_file", "open a file from the list"),
    #     ("escape", "hide_fuzzy_finder", "hide the fuzzy finder"),
    # ]
    DEFAULT_CSS = """
        FuzzyFinder {
            background: #1e1e1e 10%;
            border: round white;
            padding: 1;
            width: 100%;
            height: 100%;
            min-height: 1;
            layout: grid;
            grid-size: 2 2;
            grid-rows: 2 1fr;
        }
        FuzzyFinder > #search_bar {
            border-bottom: solid white;
            width: 98%;
        }
        FuzzyFinder > #file_list {
            height: 100%;
        }
        FuzzyFinder > #file_preview {
            row-span: 2;
            height: 100%;
            border-left: solid white;
            padding: 0 0 0 1;
        }
        FuzzyFinder > .selected_file {
            background: $surface;
            color: $text;
            text-style: reverse;
        }
        FuzzyFinder > .placeholder {
            color: $text-disabled;
        }
    """

    selected_file_line = reactive(0)
    value = reactive("")

    class FileSelected(Message, bubble=True):
        def __init__(self, sender: "FuzzyFinder", value: str) -> None:
            super().__init__()
            self.path = value
            self.fuzzy_finder = sender

    def __init__(
        self,
        id: str | None = None,  # noqa: A002
        classes: str | None = None,
    ) -> None:
        super().__init__(id=id, classes=classes)
        self.file_list: list[str | Text] = []
        self.filtered_files: list[str | Text] = []
        self.visible_files: list[str | Text] = []
        self.file_contents: dict[str, Syntax] = {}
        self.available_display_lines = 0
        self.visible_file_offset = 0
        assign_keybinds(self, "fuzzy_finder")

    def bind(
        self,
        keys: str,
        action: str,
        *,
        description: str = "",
        show: bool = True,
        key_display: str | None = None,
    ) -> None:
        self._bindings.bind(
            keys,
            action,
            description,
            show=show,
            key_display=key_display,
        )

    def compose(self) -> ComposeResult:
        yield Static(id="search_bar")
        yield Static(id="file_preview")
        yield Static(id="file_list")

    def render(self) -> RenderableType:
        result = super().render()
        self.available_display_lines = self.get_child_by_id("file_list").size.height
        return result

    def showing(self) -> None:
        placeholder_style = self.get_component_rich_style("placeholder")
        self.get_child_by_id("search_bar").update(
            Text("Search", style=placeholder_style),
        )
        files = Path(".").rglob("*.*")
        file_list = [file.as_posix() for file in files if file.is_file()]
        file_list = [file for file in file_list if ".git" not in file]
        with Path(".ignore") as ignore_file:
            if ignore_file.is_file():
                for line in ignore_file.read_text().split("\n"):
                    if line:
                        file_list = [file for file in file_list if line not in file]

        file_list.sort()
        file_list = [Text(file) for file in file_list]
        self.file_list = file_list
        self.get_files_contents()
        self.filtered_files = file_list
        self.visible_files = file_list
        if file_list:
            self.stylize_selected_line()
        self.update_file_list()
        self.show_file_contents()

    def get_files_contents(self) -> None:
        for file in self.file_list:
            with contextlib.suppress(UnicodeDecodeError):
                self.file_contents[str(file)] = Syntax.from_path(str(file))

    def show_file_contents(self) -> None:
        file = self.visible_files[self.selected_file_line]
        try:
            self.get_child_by_id("file_preview").update(self.file_contents[str(file)])
        except KeyError:
            self.get_child_by_id("file_preview").update(
                "Cannot display a non-text file",
            )

    def update_file_list(self) -> None:
        self.get_child_by_id("file_list").update(Text("\n").join(self.visible_files))

    def stylize_selected_line(self) -> None:
        if self.visible_files:
            selected_line_style = self.get_component_rich_style("selected_file")
            self.visible_files = [Text(file.plain) for file in self.visible_files]
            self.visible_files[self.selected_file_line].stylize(selected_line_style)

    def filter_files(self) -> None:
        result = list(fuzzy_finder(self.value, self.file_list))
        if len(result) < self.selected_file_line:
            self.selected_file_line = 0
        self.filtered_files = result
        self.slice_offset()
        self.stylize_selected_line()

    def slice_offset(self) -> None:
        if self.visible_file_offset:
            self.visible_files = self.filtered_files[self.visible_file_offset :]
        else:
            self.visible_files = self.filtered_files

    def check_offset_up(self) -> None:
        if (
            self.available_display_lines
            and self.selected_file_line < self.visible_file_offset
        ):
            self.visible_file_offset = self.selected_file_line

    def check_offset_down(self) -> None:
        if (
            self.available_display_lines
            and self.selected_file_line >= self.available_display_lines
        ):
            self.visible_file_offset = (
                self.selected_file_line - self.available_display_lines + 1
            )

    def action_move_up_a_file(self) -> None:
        if self.selected_file_line > 0:
            self.selected_file_line -= 1
        self.check_offset_up()
        self.slice_offset()
        self.stylize_selected_line()
        self.update_file_list()
        self.show_file_contents()

    def action_move_down_a_file(self) -> None:
        if self.selected_file_line < len(self.visible_files) - 1:
            self.selected_file_line += 1
        self.check_offset_down()
        self.slice_offset()
        self.stylize_selected_line()
        self.update_file_list()
        self.show_file_contents()

    def action_select_a_file(self) -> None:
        file = self.visible_files[self.selected_file_line]
        self.file_contents = {}
        self.file_list = []
        self.filtered_files = []
        self.visible_files = []
        self.selected_file_line = 0
        self.visible_file_offset = 0
        self.available_display_lines = 0
        self.value = ""
        self.parent.add_class("hide")
        self.post_message(self.FileSelected(self, str(file)))

    def action_hide_fuzzy_finder(self) -> None:
        self.parent.add_class("hide")
        self.app.screen.focus_previous()

    async def on_key(self, event: Key) -> None:
        if await self.handle_key(event):
            event.prevent_default()
            event.stop()
            return
        if event.is_printable:
            self.value += event.character
        if event.key == "backspace":
            self.value = self.value[:-1]
        if event.key == "backspace" or event.is_printable:
            self.selected_file_line = 0
            self.filter_files()
            if self.value:
                self.get_child_by_id("search_bar").update(self.value)
            else:
                placeholder_style = self.get_component_rich_style("placeholder")
                self.get_child_by_id("search_bar").update(
                    Text("Search", style=placeholder_style),
                )
        self.update_file_list()
