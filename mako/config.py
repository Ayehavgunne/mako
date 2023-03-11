from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import dacite
import thsl
from rich.syntax import Syntax


@dataclass
class Formatter:
    command: str = ""
    args: list[str] = field(default_factory=list)


@dataclass
class Language:
    extensions: list[str] = field(default_factory=list)
    formatter: Formatter = field(default_factory=Formatter)
    column_width: int | None = None


@dataclass
class Config:
    languages: dict[str, Language] = field(default_factory=dict)
    auto_save: bool = True
    format_on_save: bool = True

    def __post_init__(self) -> None:
        self.languages = defaultdict(Language, self.languages)

    def current_language(self, file_name: str) -> Language:
        return self.languages[Syntax.guess_lexer(file_name)]


config = Config()


def load_config(conf_dict: dict | None = None) -> Config:
    global config  # seriously reconsider this when the time comes
    if conf_dict is None:
        with (Path.home() / ".config" / "mako" / "mako.thsl").open() as config_file:
            conf_dict = thsl.load(config_file)

    config = dacite.from_dict(Config, conf_dict)
    return config


config = load_config()
