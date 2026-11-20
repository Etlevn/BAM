"""Minimal in-place progress bar for CLI batch jobs (integ / anal / nlp)."""

from __future__ import annotations

import shutil
import sys
import threading
from collections.abc import Iterable, Iterator
from typing import TypeVar

T = TypeVar("T")

_MIN_BAR_WIDTH = 10
_FALLBACK_COLS = 80

# Active bar so helpers can log above it (tqdm.write-style).
_active: ProgressBar | None = None
_active_lock = threading.Lock()


def _terminal_cols(file) -> int:
    try:
        cols = shutil.get_terminal_size(fallback=(_FALLBACK_COLS, 24)).columns
    except Exception:
        cols = _FALLBACK_COLS
    if cols <= 0:
        cols = _FALLBACK_COLS
    return cols


class ProgressBar:
    """Single-line bar on stderr; disappears on close (leave=False)."""

    def __init__(self, total: int, *, label: str = "", file=None) -> None:
        self.total = max(int(total), 0)
        self.n = 0
        self.label = str(label or "").strip()
        self.file = file if file is not None else sys.stderr
        self._closed = False
        self._tty = hasattr(self.file, "isatty") and self.file.isatty()
        self._last_len = 0
        self._lock = threading.RLock()
        self._prev_active: ProgressBar | None = None
        if self.total > 0:
            self._draw()

    def update(self, n: int = 1) -> None:
        with self._lock:
            if self._closed:
                return
            self.n = min(self.n + int(n), self.total) if self.total else self.n + int(n)
            self._draw()

    def write(self, message: str) -> None:
        """Print a log line above the bar, then redraw the bar at the bottom."""
        with self._lock:
            text = str(message).rstrip("\n") + "\n"
            if self._tty and not self._closed and self._last_len:
                self.file.write("\r" + " " * self._last_len + "\r")
                self.file.flush()
            self.file.write(text)
            self.file.flush()
            if not self._closed:
                self._draw()

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            if self._tty:
                self.file.write("\r" + " " * max(self._last_len, 1) + "\r")
                self.file.flush()
            elif self.total > 0:
                self.file.write("\n")
                self.file.flush()

    def __enter__(self) -> ProgressBar:
        global _active
        with _active_lock:
            self._prev_active = _active
            _active = self
        return self

    def __exit__(self, *exc: object) -> None:
        global _active
        self.close()
        with _active_lock:
            if _active is self:
                _active = self._prev_active

    def _bar_width(self, prefix: str, suffix: str) -> int:
        reserved = len(prefix) + len(suffix) + 2
        return max(_MIN_BAR_WIDTH, _terminal_cols(self.file) - reserved)

    def _draw(self) -> None:
        if self.total <= 0:
            return
        prefix = f"{self.label} " if self.label else ""
        suffix = f" {self.n}/{self.total}"
        width = self._bar_width(prefix, suffix)
        frac = min(self.n / self.total, 1.0)
        filled = int(width * frac)
        bar = "█" * filled + "░" * (width - filled)
        line = f"\r{prefix}|{bar}|{suffix}"
        pad = max(0, self._last_len - (len(line) - 1))
        self.file.write(line + (" " * pad))
        self._last_len = len(line) - 1 + pad
        self.file.flush()


def write_line(message: str, *, file=None) -> None:
    """Log above the active progress bar when one exists; else plain print."""
    with _active_lock:
        bar = _active
    if bar is not None and not bar._closed:
        bar.write(message)
        return
    out = file if file is not None else sys.stderr
    print(str(message).rstrip("\n"), file=out)


def track(
    iterable: Iterable[T],
    *,
    total: int | None = None,
    label: str = "",
) -> Iterator[T]:
    """
    Yield items while showing a bottom progress bar with a short label.
    The bar is cleared when the iterator is exhausted (or closed early).
    """
    if total is None:
        try:
            total = len(iterable)  # type: ignore[arg-type]
        except TypeError:
            items = list(iterable)
            total = len(items)
            iterable = items

    with ProgressBar(total if total is not None else 0, label=label) as bar:
        for item in iterable:
            yield item
            bar.update(1)
