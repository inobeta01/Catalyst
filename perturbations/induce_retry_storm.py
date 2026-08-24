"""Perturbation: Induce a retry storm by repeatedly returning failure messages."""

import time
from typing import Callable, List


class RetryStorm:
    """Wraps a function to force it to fail N times before succeeding."""

    def __init__(self, func: Callable, fail_count: int = 3):
        self.func = func
        self.fail_count = fail_count
        self.call_count = 0

    def __call__(self, *args, **kwargs):
        self.call_count += 1
        if self.call_count <= self.fail_count:
            raise ConnectionError(f"Simulated failure #{self.call_count} — retrying...")
        return self.func(*args, **kwargs)
