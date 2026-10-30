"""Tiny helper for the event stream that feeds the live "Sandbox Lifecycle" panel."""
from __future__ import annotations

import time


def ev(type_: str, **data) -> dict:
    """Build one event. Always JSON-serialisable; `t` is a unix timestamp."""
    return {"type": type_, "t": round(time.time(), 3), **data}
