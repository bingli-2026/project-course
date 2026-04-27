"""Minimal CLI entry point for the project scaffold."""

from __future__ import annotations


def build_status_message() -> str:
    """Return a stable status message for the root project scaffold."""

    return "project-course scaffold ready"


def main() -> None:
    """Run the command-line entry point."""

    print(build_status_message())
