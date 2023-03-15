from textual.app import ComposeResult
from textual.widgets import Input, Static


class FuzzyFinder(Static):
    DEFAULT_CSS = """
        FuzzyFinder {
            background: #1e1e1e 10%;
            border: round white;
            padding: 1;
            width: 100%;
            height: 100%;
            min-height: 1;
        }
    """

    def __init__(self, id: str | None = None, classes: str | None = None) -> None:
        super().__init__(id=id, classes=classes)

    def compose(self) -> ComposeResult:
        yield Input(id="search_bar")
        yield Static(id="file_list")
        yield Static(id="file_preview")
