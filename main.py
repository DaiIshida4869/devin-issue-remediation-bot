"""Top-level entry point delegating to the CLI."""

from __future__ import annotations

from app.cli import main as cli_main

if __name__ == '__main__':
    raise SystemExit(cli_main())
