import re
from collections.abc import Callable, Iterable, Iterator
from subprocess import PIPE, Popen

from rich.text import Text


def call_command(commands: list[str], std_input: str | None = None) -> tuple[str, bool]:
    process = Popen(commands, stdin=PIPE, stdout=PIPE)
    if std_input is not None:
        std_out, std_err = process.communicate(input=std_input.encode())
    else:
        std_out, std_err = process.communicate()
    if std_err:
        return std_err.decode(), False
    return std_out.decode(), True


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
