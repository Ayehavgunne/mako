import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from rich.console import RenderableType
from textual.app import App, ComposeResult, CSSPathType
from textual.containers import Grid
from textual.driver import Driver
from textual.events import Event
from textual.message import Message
from textual.widgets import DataTable, DirectoryTree, Static, Tabs

from mako.config import config
from mako.editor import Editor
from mako.footer import Footer
from mako.fuzzy_finder import FuzzyFinder
from mako.logger import mako_logger
from mako.terminal_emulator import TerminalEmulator
from mako.util import assign_keybinds, call_command


class TerminalLayer(Static):
    def compose(self) -> ComposeResult:
        yield TerminalEmulator(id="terminal")


class FuzzyFinderLayer(Static):
    def compose(self) -> ComposeResult:
        yield FuzzyFinder(id="fuzzy_finder")

    async def on_fuzzy_finder_file_selected(self, message: Message) -> None:
        self.app.get_child_by_id("base_layer").on_directory_tree_file_selected(message)


class CommandModeLayer(Static, can_focus=True):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        assign_keybinds(self, "command")

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
        yield DataTable(
            id="command_list",
            disabled=True,
            show_cursor=False,
            show_header=False,
            show_row_labels=False,
        )

    def render(self) -> RenderableType:
        table = self.get_child_by_id("command_list", DataTable)
        table.clear(columns=True)
        table_height = 18
        row_num = 0
        rows = [[] for _ in range(table_height)]
        for binding in self._bindings.keys.values():
            rows[row_num].append(f"{binding.key}: {binding.description}")
            row_num += 1
            if row_num % table_height == 0:
                row_num = 0
        table.add_columns(*rows[0])
        table.add_rows(rows)
        return ""

    async def action_show_terminal(self) -> None:
        await self.app.action_exit_command_mode()
        fuzzy_finder_layer = self.app.get_child_by_id("fuzzy_finder_layer")
        if not fuzzy_finder_layer.has_class("hide"):
            fuzzy_finder_layer.add_class("hide")
        terminal_layer = self.app.get_child_by_id("terminal_layer")
        terminal_layer.remove_class("hide")
        term = terminal_layer.get_child_by_id("terminal")
        term.get_child_by_id("content").focus()

    async def action_show_fuzzy_finder(self) -> None:
        await self.app.action_exit_command_mode()
        terminal_layer = self.app.get_child_by_id("terminal_layer")
        if not terminal_layer.has_class("hide"):
            terminal_layer.add_class("hide")
        fuzzy_finder_layer = self.app.get_child_by_id("fuzzy_finder_layer")
        fuzzy_finder_layer.remove_class("hide")
        fuzzy_finder = fuzzy_finder_layer.get_child_by_id("fuzzy_finder")
        fuzzy_finder.focus()
        fuzzy_finder.showing()


class BaseLayer(Static):
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
        yield DirectoryTree("./", id="dir_tree")
        with Grid(id="editor_grid"):  # noqa SIM117
            with Tabs(id="editor_tabs"):
                yield Editor(id="editor")
        yield Footer(id="footer")

    def on_directory_tree_file_selected(self, event: Event | Message) -> None:
        event.stop()
        editor = self.query_one(Editor)
        editor.file_path = Path(f"./{event.path}")
        editor.focus()
        self.app.sub_title = event.path

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
        result, _ = call_command(cmd)
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
        # ("ctrl+q", "quit", "exit mako"),
        # (
        #     "ctrl+space",  # this is actually ctrl+space for some reason
        #     "command_mode",
        #     "go into command mode",
        # ),
        # ("escape", "exit_command_mode", "exit command mode"),
        # ("ctrl+left", "move_to_left_widget", "move to the widget on the left"),
        # ("ctrl+right", "move_to_right_widget", "move to the widget on the right"),
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
        assign_keybinds(self, "global_keys")

    def compose(self) -> ComposeResult:
        yield BaseLayer(id="base_layer")
        yield TerminalLayer(id="terminal_layer", classes="hide")
        yield FuzzyFinderLayer(id="fuzzy_finder_layer", classes="hide")
        yield CommandModeLayer(id="command_mode_layer", classes="hide")

    async def action_command_mode(self) -> None:
        self.get_child_by_id("base_layer").query_one(Footer).update_text(
            Editor.FileChanged(Editor(), value="COMMAND MODE"),
        )
        self.get_child_by_id("command_mode_layer").remove_class("hide")
        self.get_child_by_id("command_mode_layer").focus()

    async def action_exit_command_mode(self) -> None:
        self.get_child_by_id("command_mode_layer").add_class("hide")
        self.get_child_by_id("base_layer").query_one(Footer).update_text(
            Editor.FileChanged(Editor(), value=""),
        )

    async def action_move_to_left_widget(self) -> None:
        self.screen.focus_previous()

    async def action_move_to_right_widget(self) -> None:
        self.screen.focus_next()

    def debg(self, msg: str) -> None:
        self.logger.debug(msg)


if __name__ == "__main__":
    cmd_args = sys.argv
    if len(cmd_args) > 1:
        directory = Path(cmd_args[1])
        if directory.is_dir():
            os.chdir(directory)
    app = Mako()
    app.run()
