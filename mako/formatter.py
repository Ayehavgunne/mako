from subprocess import PIPE, Popen
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mako.config import Formatter


def format_doc(value: str, formatter: "Formatter") -> str:
    command = [formatter.command, *formatter.args]
    process = Popen(command, stdin=PIPE, stdout=PIPE)
    std_out, std_err = process.communicate(value.encode())
    return std_out.decode()
