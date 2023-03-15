import asyncio
import fcntl
import os
import pty
import shlex
import struct
import termios
from asyncio import Queue

import pyte
from rich.console import RenderableType
from rich.text import Text
from textual.app import ComposeResult
from textual.events import Key
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Static


class PyteDisplay:
    def __init__(self, lines) -> None:  # noqa
        self.lines = lines

    def __rich_console__(self, _, __) -> RenderableType:  # noqa
        yield from self.lines


class Terminal(Widget, can_focus=True):
    BINDINGS = [
        ("ctrl+t", "hide_term", "hide terminal"),
    ]

    class HideMe(Message, bubble=True):
        def __init__(self, sender: "Terminal", value: bool) -> None:
            super().__init__()
            self.value = value
            self.editor = sender

    def __init__(
        self,
        send_queue: Queue,
        recv_queue: Queue,
        id: str | None = None,  # noqa
    ) -> None:
        super().__init__(id=id)
        self.ctrl_keys = {
            "left": "\u001b[D",
            "right": "\u001b[C",
            "up": "\u001b[A",
            "down": "\u001b[B",
        }
        self.recv_queue = recv_queue
        self.send_queue = send_queue
        self.nrow = 88
        self.ncol = 24
        self._screen = pyte.Screen(self.nrow, self.ncol)
        self.stream = pyte.Stream(self._screen)
        self._display = PyteDisplay([Text()])

    def on_mount(self) -> None:
        asyncio.create_task(self.recv())  # noqa

    async def action_hide_term(self) -> None:
        self.post_message(self.HideMe(self, True))

    def render(self) -> RenderableType:
        self.nrow = self.size.width
        self.ncol = self.size.height
        self._screen.resize(self.nrow, self.ncol)
        return self._display

    async def on_key(self, event: Key) -> None:
        char = self.ctrl_keys.get(event.key) or event.character
        await self.send_queue.put(["stdin", char])

    async def recv(self) -> None:
        while True:
            message = await self.recv_queue.get()
            cmd = message[0]
            if cmd == "setup":
                await self.send_queue.put(["set_size", self.nrow, self.ncol, 567, 573])
            elif cmd == "stdout":
                chars = message[1]
                self.stream.feed(chars)
                lines = []
                for i, line in enumerate(self._screen.display):
                    text = Text.from_ansi(line)
                    x = self._screen.cursor.x
                    if i == self._screen.cursor.y and x < len(text):
                        cursor = text[x]
                        cursor.stylize("reverse")
                        new_text = text[:x]
                        new_text.append(cursor)
                        new_text.append(text[x + 1 :])
                        text = new_text
                    lines.append(text)
                self._display = PyteDisplay(lines)
                self.refresh()


class TerminalEmulator(Static):
    DEFAULT_CSS = """
        TerminalEmulator {
            background: #1e1e1e 10%;
            height: 100%;
            width: 100%;
        }
        TerminalEmulator > #content {
            background: #1e1e1e;
            border: round white;
            height: 100%;
            width: 100%;
            padding: 1;
        }
    """

    class HideMe(Message, bubble=True):
        def __init__(self, sender: "TerminalEmulator", value: bool) -> None:
            super().__init__()
            self.value = value
            self.editor = sender

    def __init__(self, id: str | None = None) -> None:  # noqa: A002
        super().__init__(id=id)
        self.data_or_disconnect = None
        self.fd = self.open_terminal()
        self.p_out = os.fdopen(self.fd, "w+b", 0)
        self.recv_queue = asyncio.Queue()
        self.send_queue = asyncio.Queue()
        self.event = asyncio.Event()

    async def on_terminal_hide_me(self, message: Message) -> None:
        self.post_message(self.HideMe(self, message.value))

    def compose(self) -> ComposeResult:
        asyncio.create_task(self._run())  # noqa
        asyncio.create_task(self._send_data())  # noqa
        yield Terminal(
            self.recv_queue,
            self.send_queue,
            id="content",
        )

    @staticmethod
    def open_terminal() -> int:
        pid, fd = pty.fork()
        if pid == 0:
            argv = shlex.split("zsh")
            env = {
                "TERM": "darwin",
                "LC_ALL": "en_US.UTF-8",
                "COLUMNS": "88",
                "LINES": "24",
            }
            os.execvpe(argv[0], argv, env)
        return fd

    async def _run(self) -> None:
        loop = asyncio.get_running_loop()

        def on_output() -> None:
            try:
                self.data_or_disconnect = self.p_out.read(65536).decode()
                self.event.set()
            except Exception:  # noqa
                loop.remove_reader(self.p_out)
                self.data_or_disconnect = None
                self.event.set()

        loop.add_reader(self.p_out, on_output)
        await self.send_queue.put(["setup", {}])
        while True:
            msg = await self.recv_queue.get()
            if msg[0] == "stdin":
                self.p_out.write(msg[1].encode())
            elif msg[0] == "set_size":
                winsize = struct.pack("HH", msg[1], msg[2])
                fcntl.ioctl(self.fd, termios.TIOCSWINSZ, winsize)

    async def _send_data(self) -> None:
        while True:
            await self.event.wait()
            self.event.clear()
            if self.data_or_disconnect is None:
                await self.send_queue.put(["disconnect", 1])
            else:
                await self.send_queue.put(["stdout", self.data_or_disconnect])
