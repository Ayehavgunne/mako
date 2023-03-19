import re
from collections.abc import Callable, Iterable, Iterator
from dataclasses import fields
from subprocess import PIPE, Popen

from rich.text import Text
from textual.app import App
from textual.widget import Widget

from mako.config import config


action_description_map = {
    "quit": "exit mako",
    "show_terminal": "show terminal",
    "show_fuzzy_finder": "show fuzzy finder",
    "command_mode": "go into command mode",
    "exit_command_mode": "exit command mode",
    "cursor_left": "move cursor left",
    "cursor_right": "move cursor right",
    "cursor_up": "move cursor up",
    "cursor_down": "move cursor down",
    "delete_left": "delete left of cursor",
    "delete_right": "delete right of cursor",
    "home": "go to beginning of line",
    "end": " go to end of line",
    "add_tab": "add a tab or tabs worth of spaces",
    "save_file": "save file to disk",
    "copy": "copy selection to system clipboard",
    "paste": "paste contents from system clipboard at cursor",
    "move_to_left_widget": "move to the widget on the left",
    "move_to_right_widget": "move to the widget on the right",
    "move_up_a_file": "move file selector up one in the list",
    "move_down_a_file": "move file selector down one in the list",
    "select_a_file": "open a file from the list",
    "hide_fuzzy_finder": "hide the fuzzy finder",
    "hide_terminal": "hide the terminal",
}


def call_command(commands: list[str], std_input: str | None = None) -> tuple[str, bool]:
    process = Popen(commands, stdin=PIPE, stdout=PIPE)
    if std_input is not None:
        std_out, std_err = process.communicate(input=std_input.encode())
    else:
        std_out, std_err = process.communicate()
    if std_err:
        return std_err.decode(), False
    return std_out.decode(), True


def assign_keybinds(widget: Widget | App, keybind_type: str) -> None:
    keybinds = getattr(config.keybinds, keybind_type)
    for field in fields(keybinds):
        key = field.name
        action = getattr(keybinds, key)
        desc = action_description_map[action]
        if "_space" in key:
            key = key.replace("_space", "_@")
        widget.bind(key.replace("_", "+"), action, description=desc)


def fuzzy_finder(
    input_str: str,
    collection: Iterable[str],
    accessor: Callable = lambda x: x,
    sort_results: bool = True,
) -> Iterator[Text]:
    """
    From https://github.com/amjith/fuzzyfinder
    """
    suggestions = []
    input_str = str(input_str) if not isinstance(input_str, str) else input_str
    pat = ".*?".join(map(re.escape, input_str))
    pat = f"(?=({pat}))"
    regex = re.compile(pat, re.IGNORECASE)
    for item in collection:
        item = str(item)
        r = list(regex.finditer(accessor(item)))
        if r:
            best = min(r, key=lambda x: len(x.group(1)))
            suggestions.append((len(best.group(1)), best.start(), accessor(item), item))

    if sort_results:
        return (Text(z[-1]) for z in sorted(suggestions))
    return (Text(z[-1]) for z in sorted(suggestions, key=lambda x: x[:2]))


# try https://github.com/seatgeek/thefuzz


def fuzzy_finder_2(text: str, collection: Iterable[str]) -> Iterator[Text]:
    results = []

    for string in collection:
        string = str(string)
        key = []

        for x in text:
            index = string.find(x)
            if index == -1:
                break
            key.append(index)
        else:
            results.append((key, string))

    return (Text(y) for _, y in sorted(results))
