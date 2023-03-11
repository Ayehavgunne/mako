from dataclasses import dataclass, field
from pathlib import Path

import dacite
import thsl


@dataclass
class Formatter:
    command: str = ""
    args: list[str] = field(default_factory=list)


@dataclass
class Language:
    name: str = ""
    extensions: list[str] = field(default_factory=list)
    formatter: Formatter = field(default_factory=Formatter)
    column_width: int = 88


@dataclass
class Config:
    languages: list[Language] = field(default_factory=list)


config = Config()


def load_config(conf_dict: dict | None = None) -> Config:
    global config  # seriously reconsider this when the time comes
    if conf_dict is None:
        with (Path.home() / ".config" / "mako" / "mako.thsl").open() as config_file:
            conf_dict = thsl.load(config_file)
    config = dacite.from_dict(Config, conf_dict)
    return config


config = load_config()
