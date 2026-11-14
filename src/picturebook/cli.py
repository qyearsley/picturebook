"""The `picturebook` command. Each subcommand is one module's main()."""

from __future__ import annotations

import importlib
import sys

from . import __version__

# name: (module, one-line summary). The order is the order of the work.
COMMANDS = {
    "prompts": ("prompts", "write text-and-prompts.md, the book's text and prompts for review"),
    "check": ("check", "check the verse form or sentence count of each page"),
    "placeholders": ("placeholders", "write labelled stand-in images for missing art"),
    "styles": ("styles", "try a few pages in several art styles (Replicate)"),
    "generate": ("generate", "generate art candidates, or a paste queue for any service"),
    "pick": ("pick", "rebuild pick.html, the page where you choose candidates"),
    "import": ("importer", "file picked or provided images under their page names"),
    "text-positions": ("textpos", "set each page's text band from its prompt"),
    "pdf": ("pdf", "build one PDF of a book"),
    "reader": ("reader", "build the HTML reader of a book"),
    "print": ("editions", "build every print edition of one or more books"),
}


def usage() -> str:
    width = max(len(name) for name in COMMANDS)
    lines = [
        "usage: picturebook <command> [options]",
        "",
        "Make bilingual picture books: text and prompts in, print PDFs and an HTML reader out.",
        "",
        "commands:",
    ]
    lines += [f"  {name:<{width}}  {summary}" for name, (_, summary) in COMMANDS.items()]
    lines += ["", "Run `picturebook <command> --help` for a command's options."]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(usage())
        return
    if argv[0] in ("-V", "--version"):
        print(f"picturebook {__version__}")
        return
    name, rest = argv[0], argv[1:]
    if name not in COMMANDS:
        sys.exit(f"picturebook: unknown command {name!r}\n\n{usage()}")
    module = importlib.import_module(f".{COMMANDS[name][0]}", __package__)
    # argparse takes the program name for its usage line from argv[0].
    sys.argv[0] = f"picturebook {name}"
    module.main(rest)
