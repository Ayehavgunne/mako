import subprocess
from collections import defaultdict
from pathlib import Path

from textual.app import App, ComposeResult, CSSPathType
from textual.containers import Grid
from textual.driver import Driver
from textual.events import Event
from textual.message import Message
from textual.widgets import ContentSwitcher, DirectoryTree, Static

from mako.config import config
from mako.editor import Editor
from mako.footer import Footer
from mako.logger import mako_logger
from mako.terminal_emulator import TerminalEmulator


class SecondLayer(Static):
    def compose(self) -> ComposeResult:
        yield TerminalEmulator(id="term")


class BaseLayer(Static):
    BINDINGS = [
        ("ctrl+left", "move_to_left_widget", "move to the widget on the left"),
        ("ctrl+right", "move_to_right_widget", "move to the widget on the right"),
        ("ctrl+t", "toggle_term", "show/hide terminal"),
    ]

    def compose(self) -> ComposeResult:
        yield DirectoryTree("./", id="dir_tree")
        with Grid(id="editor_grid"):  # noqa SIM117
            with ContentSwitcher(initial="editor", id="editor_tabs"):
                yield Editor(id="editor")
        yield Footer(id="footer")

    def on_directory_tree_file_selected(self, event: Event) -> None:
        event.stop()
        editor = self.query_one(Editor)
        editor.file_path = Path(f"./{event.path}")
        editor.focus()
        self.app.sub_title = event.path

    async def action_move_to_left_widget(self) -> None:
        self.screen.focus_previous()

    async def action_move_to_right_widget(self) -> None:
        self.screen.focus_next()

    async def action_toggle_term(self) -> None:
        second_layer = self.app.get_child_by_id("second_layer")
        if second_layer.has_class("hide"):
            second_layer.remove_class("hide")
            term = second_layer.get_child_by_id("term")
            term.get_child_by_id("content").focus()
        else:
            second_layer.add_class("hide")
            self.screen.focus_previous()

    async def on_editor_file_changed(self, message: Message) -> None:
        self.query_one(Footer).update_text(message)

    async def on_editor_cursor_line_changed(self, message: Message) -> None:
        self.query_one(Footer).update_text(message)

    async def on_editor_cursor_column_changed(self, message: Message) -> None:
        self.query_one(Footer).update_text(message)

    def on_mount(self) -> None:
        self.query_one(DirectoryTree).focus()
        self.get_git_diff_lines()

    def get_git_diff_lines(self) -> None:
        cmd = ["bash", "./mako/diff_script.sh"]
        result = subprocess.run(cmd, capture_output=True)
        result = result.stdout.decode()
        diff_lines = {}
        for line in result.split("\n"):
            line_parts = line.split(":|:")
            if len(line_parts) > 1 and line_parts[2][0] in ("-", "+"):
                diff_tuple = (line_parts[1], line_parts[2][0])
                if line_parts[0] in diff_lines:
                    diff_lines[line_parts[0]].add(diff_tuple)
                else:
                    diff_lines[line_parts[0]] = {diff_tuple}
        diff_lines = {
            key: sorted(list(value), key=lambda x: int(x[0]))
            for key, value in diff_lines.items()
        }
        self.app.git_working_changes = defaultdict(list, diff_lines)


class Mako(App):
    CSS_PATH = "app.css"
    BINDINGS = [
        ("ctrl+c", "", ""),
        ("ctrl+q", "quit", "Exit Mako"),
    ]

    def __init__(
        self,
        driver_class: type[Driver] | None = None,
        css_path: CSSPathType | None = None,
        watch_css: bool = False,
    ) -> None:
        super().__init__(driver_class, css_path, watch_css)
        self.config = config
        self.logger = mako_logger
        self.git_working_changes = defaultdict(list)

    def compose(self) -> ComposeResult:
        yield BaseLayer(id="base_layer")
        yield SecondLayer(id="second_layer", classes="hide")

    async def on_terminal_emulator_hide_me(self, _: Message) -> None:
        await self.get_child_by_id("base_layer").action_toggle_term()


if __name__ == "__main__":
    app = Mako()
    app.run()
