from pathlib import Path
from typing import TYPE_CHECKING

from textual.app import App, ComposeResult, CSSPathType
from textual.widgets import ContentSwitcher, DirectoryTree

from mako.editor import Editor
from mako.logger import mako_logger

if TYPE_CHECKING:
    from textual.driver import Driver
    from textual.events import Event


class Mako(App):
    CSS_PATH = "horizontal_layout.css"
    BINDINGS = [
        (
            "ctrl+left",
            "move_to_left_widget",
            "move to the widget on the left",
        ),
        (
            "ctrl+right",
            "move_to_right_widget",
            "move to the widget on the right",
        ),
    ]

    def __init__(
        self,
        driver_class: type["Driver"] | None = None,
        css_path: CSSPathType | None = None,
        watch_css: bool = False,
    ) -> None:
        super().__init__(driver_class, css_path, watch_css)
        self.bind("ctrl+c", "", description="Copy", show=False)
        self.bind("ctrl+q", "quit", description="Exit Mako", show=False)

    def compose(self) -> ComposeResult:
        yield DirectoryTree("./", classes="side_panel", id="dir_tree")
        with ContentSwitcher(initial="editor"):
            yield Editor(classes="box", id="editor")

    def on_directory_tree_file_selected(self, event: "Event") -> None:
        event.stop()
        editor = self.query_one(Editor)
        editor.file_path = Path(f"./{event.path}")
        editor.focus()
        self.sub_title = event.path

    async def action_move_to_left_widget(self) -> None:
        self.screen.focus_previous()

    async def action_move_to_right_widget(self) -> None:
        self.screen.focus_next()

    def on_mount(self) -> None:
        self.query_one(DirectoryTree).focus()


if __name__ == "__main__":
    mako_logger.debug("mako start")
    app = Mako()
    app.run()
