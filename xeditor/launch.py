"""Qt-free application launcher with single-instance hand-off."""

from __future__ import annotations

import os

from .single_instance import acquire_instance, command_line_files


def main() -> int:
    if os.environ.get("XEDITOR_ALLOW_MULTIPLE") != "1":
        files = command_line_files()
        if not acquire_instance(files):
            # Another XEditor is already running; it will activate itself and
            # open the requested file. Do not import Qt in this process.
            return 0

    # Import Qt only after the single-instance check has succeeded.
    from .app import run

    return run()
