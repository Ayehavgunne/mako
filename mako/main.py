from pathlib import Path

from textual.app import App, ComposeResult, CSSPathType
from textual.driver import Driver
from textual.events import Event
from textual.message import Message
from textual.screen import Screen
from textual.widgets import ContentSwitcher, DirectoryTree

from mako.config import config
from mako.editor import Editor
from mako.footer import Footer
from mako.logger import mako_logger

from mako.terminal_emulator import TerminalEmulator


class TerminalScreen(Screen):
    BINDINGS = [("escape", "app.pop_screen", "Pop screen")]

    def compose(self) -> ComposeResult:
        yield TerminalEmulator()


class MainScreen(Screen):
    BINDINGS = [
        ("ctrl+left", "move_to_left_widget", "move to the widget on the left"),
        ("ctrl+right", "move_to_right_widget", "move to the widget on the right"),
        ("ctrl+t", "show_new_terminal", "show a modal with a terminal"),
    ]

    def compose(self) -> ComposeResult:
        yield DirectoryTree("./", classes="side_panel", id="dir_tree")
        # with Grid():
        with ContentSwitcher(initial="editor", id="editor_tabs"):
            yield Editor(classes="box", id="editor")
        yield Footer(id="footer")

    def on_directory_tree_file_selected(self, event: Event) -> None:
        event.stop()
        editor = self.query_one(Editor)
        editor.file_path = Path(f"./{event.path}")
        editor.focus()
        self.app.sub_title = event.path

    async def action_move_to_left_widget(self) -> None:
        self.focus_previous()

    async def action_move_to_right_widget(self) -> None:
        self.focus_next()

    async def action_show_new_terminal(self) -> None:
        await self.app.push_screen(TerminalScreen())

    async def on_editor_file_changed(self, message: Message) -> None:
        self.query_one(Footer).update_text(message)

    async def on_editor_cursor_line_changed(self, message: Message) -> None:
        self.query_one(Footer).update_text(message)

    async def on_editor_cursor_column_changed(self, message: Message) -> None:
        self.query_one(Footer).update_text(message)

    def on_mount(self) -> None:
        self.query_one(DirectoryTree).focus()


class Mako(App):
    CSS_PATH = "app.css"
    SCREENS = {"main": MainScreen()}
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

    # def compose(self) -> ComposeResult:
    #     yield DirectoryTree("./", classes="side_panel", id="dir_tree")
    #     # with Grid():
    #     with ContentSwitcher(initial="editor", id="editor_tabs"):
    #         yield Editor(classes="box", id="editor")
    #     yield Footer(id="footer")

    # def on_directory_tree_file_selected(self, event: Event) -> None:
    #     event.stop()
    #     editor = self.query_one(Editor)
    #     editor.file_path = Path(f"./{event.path}")
    #     editor.focus()
    #     self.sub_title = event.path
    #
    # async def action_move_to_left_widget(self) -> None:
    #     self.focus_previous()
    #
    # async def action_move_to_right_widget(self) -> None:
    #     self.focus_next()
    #
    # async def action_show_new_terminal(self) -> None:
    #     await self.push_screen(TerminalScreen())
    #
    # async def on_editor_file_changed(self, message: Message) -> None:
    #     self.query_one(Footer).update_text(message)
    #
    # async def on_editor_cursor_line_changed(self, message: Message) -> None:
    #     self.query_one(Footer).update_text(message)
    #
    # async def on_editor_cursor_column_changed(self, message: Message) -> None:
    #     self.query_one(Footer).update_text(message)
    #
    def on_mount(self) -> None:
        self.push_screen("main")


if __name__ == "__main__":
    app = Mako()
    app.run()
