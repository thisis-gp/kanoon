"""Errors shared across modules. Busy -> HTTP 503 with Retry-After (never queue unbounded work)."""


class Busy(Exception):
    """A bounded resource (inference slot, DB slot, LLM slot) is full; the caller should retry later."""

    def __init__(self, what="server busy", retry_after=5):
        super().__init__(what)
        self.what, self.retry_after = what, retry_after
