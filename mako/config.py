from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import dacite
import thsl
from rich.syntax import Syntax


def default_brackets() -> dict[str, str]:
    return {
        "[": "]",
        "(": ")",
        "{": "}",
        "'": "'",
        '"': '"',
        "<": ">",
    }


@dataclass
class Formatter:
    command: str = ""
    args: list[str] = field(default_factory=list)


@dataclass
class Language:
    extensions: list[str] = field(default_factory=list)
    formatter: Formatter = field(default_factory=Formatter)
    column_width: int | None = None
    tab_size: int = 4
    word_wrap: bool = False
    indent_guides: bool = True
    line_numbers: bool = True
    auto_indent: bool = True
    auto_brackets: bool = True
    bracket_pairs: dict[str] = field(default_factory=default_brackets)


@dataclass
class GlobalKeys:
    ctrl_q: str = "quit"
    ctrl_space: str = "command_mode"
    escape: str = "exit_command_mode"
    ctrl_left: str = "move_to_left_widget"
    ctrl_right: str = "move_to_right_widget"


@dataclass
class EditMode:
    up: str = "cursor_up"
    down: str = "cursor_down"
    left: str = "cursor_left"
    right: str = "cursor_right"
    backspace: str = "delete_left"
    delete: str = "delete_right"
    home: str = "home"
    end: str = "end"
    tab: str = "add_tab"
    ctrl_s: str = "add_tab"
    ctrl_c: str = "copy"
    ctrl_p: str = "paste"


@dataclass
class CommandMode:
    f: str = "show_fuzzy_finder"
    t: str = "show_terminal"


@dataclass
class SelectMode:
    up: str = "cursor_up"


@dataclass
class FuzzyFinderMode:
    up: str = "move_up_a_file"
    down: str = "move_down_a_file"
    enter: str = "select_a_file"
    escape: str = "hide_fuzzy_finder"


@dataclass
class TerminalMode:
    escape: str = "hide_terminal"


@dataclass
class Keybinds:
    global_keys: GlobalKeys = field(default_factory=GlobalKeys)
    edit: EditMode = field(default_factory=EditMode)
    command: CommandMode = field(default_factory=CommandMode)
    select: SelectMode = field(default_factory=SelectMode)
    fuzzy_finder: FuzzyFinderMode = field(default_factory=FuzzyFinderMode)
    terminal: TerminalMode = field(default_factory=TerminalMode)


@dataclass
class Config:
    languages: dict[str, Language] = field(default_factory=dict)
    keybinds: Keybinds = field(default_factory=Keybinds)
    auto_save: bool = True
    format_on_save: bool = True
    highlight_line: bool = True

    def __post_init__(self) -> None:
        self.languages = defaultdict(Language, self.languages)

    def get_language(self, file_name: str) -> Language:
        return self.languages[Syntax.guess_lexer(file_name)]


config = Config()


def load_config(conf_dict: dict | None = None) -> Config:
    global config  # noqa: seriously reconsider this when the time comes
    if conf_dict is None:
        with (Path.home() / ".config" / "mako" / "mako.thsl").open() as config_file:
            conf_dict = thsl.load(config_file)

    config = dacite.from_dict(Config, conf_dict)
    return config


config = load_config()
