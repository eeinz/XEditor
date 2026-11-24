"""Single-instance guard and activation hand-off.

This module is intentionally Qt-free: it must be imported before PySide6 so
that a duplicate launch can exit cleanly even while another copy holds the
one-file runtime's DLLs.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

_MUTEX_NAME = "Local\\XEditor.SingleInstance.v1"
_ACTIVATION_FILE = Path(tempfile.gettempdir()) / "XEditor.activate.json"
_mutex_handle = None
_unix_lock_fd: int | None = None


def _write_activation(files: list[str] | None) -> None:
    payload = {"files": [str(item) for item in (files or [])][:8]}
    try:
        _ACTIVATION_FILE.parent.mkdir(parents=True, exist_ok=True)
        _ACTIVATION_FILE.write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8"
        )
    except OSError:
        pass


def _find_existing_window() -> int | None:
    """Find a visible window belonging to an existing XEditor.exe process.

    This also handles older builds that predate the single-instance mutex, so
    upgrading cannot trigger the one-file Qt DLL lock again.
    """
    if os.name != "nt":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        user32.GetWindowThreadProcessId.argtypes = (
            wintypes.HWND,
            ctypes.POINTER(wintypes.DWORD),
        )
        user32.GetWindowTextLengthW.argtypes = (wintypes.HWND,)
        user32.GetWindowTextLengthW.restype = ctypes.c_int
        kernel32.OpenProcess.argtypes = (
            wintypes.DWORD,
            wintypes.BOOL,
            wintypes.DWORD,
        )
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.QueryFullProcessImageNameW.argtypes = (
            wintypes.HANDLE,
            wintypes.DWORD,
            wintypes.LPWSTR,
            ctypes.POINTER(wintypes.DWORD),
        )
        kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)

        def process_name(pid: int) -> str:
            handle = kernel32.OpenProcess(0x1000, False, pid)  # LIMITED_INFORMATION
            if not handle:
                return ""
            try:
                buffer = ctypes.create_unicode_buffer(1024)
                size = wintypes.DWORD(len(buffer))
                if kernel32.QueryFullProcessImageNameW(
                    handle, 0, buffer, ctypes.byref(size)
                ):
                    return Path(buffer.value).name.lower()
            finally:
                kernel32.CloseHandle(handle)
            return ""

        found: list[int] = []
        enum_proc = ctypes.WINFUNCTYPE(
            wintypes.BOOL, wintypes.HWND, wintypes.LPARAM
        )

        def callback(hwnd, _lparam):
            if not user32.IsWindowVisible(hwnd):
                return True
            if user32.GetWindowTextLengthW(hwnd) <= 0:
                return True
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if not pid.value or pid.value == os.getpid():
                return True
            if process_name(pid.value) == "xeditor.exe":
                found.append(int(hwnd))
                return False
            return True

        callback_ref = enum_proc(callback)
        user32.EnumWindows(callback_ref, 0)
        return found[0] if found else None
    except Exception:
        return None



def _clear_activation() -> None:
    try:
        _ACTIVATION_FILE.unlink(missing_ok=True)
    except OSError:
        pass


def acquire_instance(files: list[str] | None = None) -> bool:
    """Acquire the per-session lock.

    Returns True for the primary instance and False for a duplicate launch
    (which writes an activation request for the running instance first).
    """
    global _mutex_handle, _unix_lock_fd

    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        try:
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.CreateMutexW.argtypes = (
                wintypes.LPCVOID,
                wintypes.BOOL,
                wintypes.LPCWSTR,
            )
            kernel32.CreateMutexW.restype = wintypes.HANDLE
            kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
            handle = kernel32.CreateMutexW(None, False, _MUTEX_NAME)
            if not handle:
                return True  # fail open rather than make the app unusable
            if ctypes.get_last_error() == 183:  # ERROR_ALREADY_EXISTS
                kernel32.CloseHandle(handle)
                _write_activation(files)
                return False
            _mutex_handle = handle
        except Exception:
            return True
    else:
        try:
            import fcntl

            lock_path = Path(tempfile.gettempdir()) / "XEditor.instance.lock"
            fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                os.close(fd)
                _write_activation(files)
                return False
            _unix_lock_fd = fd
        except Exception:
            return True

    # An older XEditor build does not know about the mutex above. If its main
    # window is still open, focus it instead of starting a second Qt instance.
    existing_window = _find_existing_window()
    if existing_window is not None:
        bring_window_to_front(existing_window)
        return False

    _clear_activation()
    return True


def has_pending_activation() -> bool:
    return _ACTIVATION_FILE.exists()


def consume_activation_request() -> dict | None:
    """Read and remove the activation request written by a duplicate launch."""
    if not _ACTIVATION_FILE.exists():
        return None
    try:
        text = _ACTIVATION_FILE.read_text(encoding="utf-8")
    except OSError:
        return None
    _clear_activation()
    try:
        payload = json.loads(text)
    except (ValueError, TypeError):
        payload = {}
    return payload if isinstance(payload, dict) else {}


def bring_window_to_front(window_id: int) -> None:
    """Best-effort Windows foreground activation for the primary window."""
    if os.name != "nt":
        return
    try:
        import ctypes

        user32 = ctypes.windll.user32
        user32.ShowWindow(window_id, 9)  # SW_RESTORE
        user32.SetForegroundWindow(window_id)
    except Exception:
        pass


def command_line_files(argv: list[str] | None = None) -> list[str]:
    """Return existing file arguments from the command line."""
    files: list[str] = []
    for arg in (argv if argv is not None else sys.argv[1:]):
        if not arg or arg.startswith("-"):
            continue
        try:
            path = Path(arg).expanduser().resolve()
        except OSError:
            continue
        if path.is_file():
            files.append(str(path))
    return files
