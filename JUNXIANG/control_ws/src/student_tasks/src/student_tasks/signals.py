"""Scoped cancellation-only handlers for process termination signals."""

from __future__ import annotations

import signal
import threading
from dataclasses import dataclass
from types import FrameType
from typing import Mapping


WATCHED_SIGNALS = (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)


@dataclass(frozen=True)
class SignalCancellationState:
    cancelled: bool
    signal_number: int | None
    signal_name: str | None
    installed: bool
    restored: bool


class SignalCancellationGuard:
    """A cancellation token whose handler performs no I/O or cleanup."""

    def __init__(self) -> None:
        self._event = threading.Event()
        self._signal_number: int | None = None
        self._installed = False
        self._restored = False
        self._previous: Mapping[int, object] = {}

    @property
    def state(self) -> SignalCancellationState:
        number = self._signal_number
        return SignalCancellationState(
            cancelled=self._event.is_set(),
            signal_number=number,
            signal_name=None if number is None else signal.Signals(number).name,
            installed=self._installed,
            restored=self._restored,
        )

    def is_cancelled(self) -> bool:
        return self._event.is_set()

    def handle_signal(self, signum: int, frame: FrameType | object | None) -> None:
        del frame
        if self._signal_number is None:
            self._signal_number = int(signum)
        self._event.set()

    def __enter__(self) -> "SignalCancellationGuard":
        if self._installed:
            raise RuntimeError("signal guard is already installed")
        self._previous = {number: signal.getsignal(number) for number in WATCHED_SIGNALS}
        for number in WATCHED_SIGNALS:
            signal.signal(number, self.handle_signal)
        self._installed = True
        self._restored = False
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        del exc_type, exc, traceback
        for number, handler in self._previous.items():
            signal.signal(number, handler)
        self._installed = False
        self._restored = True
