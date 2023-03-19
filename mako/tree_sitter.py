from tree_sitter import Language, Parser

LANGUAGE_FILE = "tree_sitter_languages/languages.so"

JS_LANGUAGE = Language(LANGUAGE_FILE, "javascript")
PY_LANGUAGE = Language(LANGUAGE_FILE, "python")


PY_PARSER = Parser()
PY_PARSER.set_language(PY_LANGUAGE)


def add_new_language() -> None:
    Language.build_library(
        # Store the library in the `build` directory
        ".mako/tree_sitter_languages/languages.so",
        # Include one or more languages
        [],
    )
