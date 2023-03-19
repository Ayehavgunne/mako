from collections.abc import Iterable
from pathlib import Path

from pygments.lexer import Lexer
from pygments.token import Comment
from rich._loop import loop_first
from rich.console import Console, ConsoleOptions

from rich.containers import Lines
from rich.padding import PaddingDimensions
from rich.segment import Segment
from rich.style import Style
from rich.syntax import DEFAULT_THEME, Syntax, SyntaxTheme
from rich.text import Text


class CustomSyntax(Syntax):
    def __init__(
        self,
        code: str,
        lexer: Lexer | str,
        *,
        theme: str | SyntaxTheme = DEFAULT_THEME,
        dedent: bool = False,
        line_numbers: bool = False,
        start_line: int = 1,
        column_offset: int = 0,
        line_range: tuple[int | None, int | None] | None = None,
        highlight_lines: set[int] | None = None,
        code_width: int | None = None,
        tab_size: int = 4,
        word_wrap: bool = False,
        background_color: str | None = None,
        indent_guides: bool = False,
        padding: PaddingDimensions = 0,
    ) -> None:
        super().__init__(
            code,
            lexer,
            theme=theme,
            dedent=dedent,
            line_numbers=line_numbers,
            start_line=start_line,
            line_range=line_range,
            highlight_lines=highlight_lines,
            code_width=code_width,
            tab_size=tab_size,
            word_wrap=word_wrap,
            background_color=background_color,
            indent_guides=indent_guides,
            padding=padding,
        )
        self.column_offset = column_offset

    @classmethod
    def from_path(
        cls,
        path: str,
        encoding: str = "utf-8",
        lexer: Lexer | str | None = None,
        theme: str | SyntaxTheme = DEFAULT_THEME,
        dedent: bool = False,
        line_numbers: bool = False,
        line_range: tuple[int | None, int | None] | None = None,
        start_line: int = 1,
        column_offset: int = 0,
        highlight_lines: set[int] | None = None,
        code_width: int | None = None,
        tab_size: int = 4,
        word_wrap: bool = False,
        background_color: str | None = None,
        indent_guides: bool = False,
        padding: PaddingDimensions = 0,
    ) -> "Syntax":
        code = Path(path).read_text(encoding=encoding)

        if not lexer:
            lexer = cls.guess_lexer(path, code=code)

        return cls(
            code,
            lexer,
            theme=theme,
            dedent=dedent,
            line_numbers=line_numbers,
            line_range=line_range,
            column_offset=column_offset,
            start_line=start_line,
            highlight_lines=highlight_lines,
            code_width=code_width,
            tab_size=tab_size,
            word_wrap=word_wrap,
            background_color=background_color,
            indent_guides=indent_guides,
            padding=padding,
        )

    def _get_syntax(  # noqa: PLR0912, PLR0915
        self,
        console: Console,
        options: ConsoleOptions,
    ) -> Iterable[Segment]:
        """
        Get the Segments for the Syntax object, excluding any vertical/horizontal padding
        """  # noqa: E501
        transparent_background = self._get_base_style().transparent_background
        code_width = (
            (
                (options.max_width - self._numbers_column_width - 1)
                if self.line_numbers
                else options.max_width
            )
            if self.code_width is None
            else self.code_width
        )

        ends_on_nl, processed_code = self._process_code(self.code)
        text = self.highlight(processed_code, self.line_range)

        if (
            not self.line_numbers
            and not self.word_wrap
            and not self.line_range
            and not self.column_offset
        ):
            if not ends_on_nl:
                text.remove_suffix("\n")
            # Simple case of just rendering text
            style = (
                self._get_base_style()
                + self._theme.get_style_for_token(Comment)
                + Style(dim=True)
                + self.background_style
            )
            if self.indent_guides and not options.ascii_only:
                text = text.with_indent_guides(self.tab_size, style=style)
                text.overflow = "crop"
            if style.transparent_background:
                yield from console.render(
                    text,
                    options=options.update(width=code_width),
                )
            else:
                syntax_lines = console.render_lines(
                    text,
                    options.update(width=code_width, height=None, justify="left"),
                    style=self.background_style,
                    pad=True,
                    new_lines=True,
                )
                for syntax_line in syntax_lines:
                    yield from syntax_line
            return

        start_line, end_line = self.line_range or (None, None)
        line_offset = 0
        if start_line:
            line_offset = max(0, start_line - 1)
        lines: list[Text] | Lines = text.split("\n", allow_blank=ends_on_nl)
        if self.line_range:
            if line_offset > len(lines):
                return
            lines = lines[line_offset:end_line]

        if self.column_offset:
            col_start = self.column_offset
            col_end = col_start + self.code_width if self.code_width else None
            line_sections = []
            for line in lines:
                if col_start > len(line):
                    line_section = Text("")
                else:
                    if col_end is None:  # noqa: PLR5501
                        line_section = line[col_start:]
                    else:
                        line_section = line[col_start:col_end]
                line_sections.append(line_section)
            lines = line_sections

        if self.indent_guides and not options.ascii_only:
            style = (
                self._get_base_style()
                + self._theme.get_style_for_token(Comment)
                + Style(dim=True)
                + self.background_style
            )
            lines = (
                Text("\n")
                .join(lines)
                .with_indent_guides(self.tab_size, style=style)
                .split("\n", allow_blank=True)
            )

        numbers_column_width = self._numbers_column_width
        render_options = options.update(width=code_width)

        highlight_line = self.highlight_lines.__contains__
        _Segment = Segment  # noqa: N806
        new_line = _Segment("\n")

        line_pointer = "> " if options.legacy_windows else "❱ "

        (
            background_style,
            number_style,
            highlight_number_style,
        ) = self._get_number_styles(console)

        for line_no, line in enumerate(lines, self.start_line + line_offset):
            if self.word_wrap:
                wrapped_lines = console.render_lines(
                    line,
                    render_options.update(height=None, justify="left"),
                    style=background_style,
                    pad=not transparent_background,
                )
            else:
                segments = list(line.render(console, end=""))
                if options.no_wrap:
                    wrapped_lines = [segments]
                else:
                    wrapped_lines = [
                        _Segment.adjust_line_length(
                            segments,
                            render_options.max_width,
                            style=background_style,
                            pad=not transparent_background,
                        ),
                    ]

            if self.line_numbers:
                wrapped_line_left_pad = _Segment(
                    " " * numbers_column_width + " ",
                    background_style,
                )
                for first, wrapped_line in loop_first(wrapped_lines):
                    if first:
                        line_column = str(line_no).rjust(numbers_column_width - 2) + " "
                        if highlight_line(line_no):
                            yield _Segment(line_pointer, Style(color="red"))
                            yield _Segment(line_column, highlight_number_style)
                        else:
                            yield _Segment("  ", highlight_number_style)
                            yield _Segment(line_column, number_style)
                    else:
                        yield wrapped_line_left_pad
                    yield from wrapped_line
                    yield new_line
            else:
                for wrapped_line in wrapped_lines:
                    yield from wrapped_line
                    yield new_line
