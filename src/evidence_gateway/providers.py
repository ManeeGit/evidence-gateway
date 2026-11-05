"""Side-effect-free provider contract, with an offline extractive baseline."""

from collections.abc import Callable
import re
import threading
import time
from typing import Protocol
from .models import Claim, Hit
from .retrieval import tokens


class Provider(Protocol):
    name: str

    def generate(self, question: str, hits: list[Hit]) -> tuple[Claim, ...]: ...


class ExtractiveProvider:
    name = "extractive-v1"

    def generate(self, question: str, hits: list[Hit]) -> tuple[Claim, ...]:
        query = set(tokens(question))
        candidates = []
        for hit in hits:
            for sentence in re.split(r"(?<=[.!?])\s+|\n+", hit.chunk.text):
                score = len(query & set(tokens(sentence)))
                if score and 0 < len(sentence) <= 600:
                    candidates.append((score, hit.score, hit.chunk.id, sentence))
        candidates.sort(key=lambda item: (-item[0], -item[1], item[2], item[3]))
        return tuple(Claim(item[2], item[3]) for item in candidates[:2])


class CircuitOpen(Exception):
    pass


class CircuitBreaker:
    """Process-local breaker. A single half-open probe prevents a retry stampede."""

    def __init__(
        self,
        threshold: int = 3,
        recovery_seconds: float = 30.0,
        clock: Callable[[], float] = time.monotonic,
    ):
        if threshold < 1 or recovery_seconds <= 0:
            raise ValueError("Invalid circuit breaker configuration")
        self.threshold = threshold
        self.recovery_seconds = recovery_seconds
        self.clock = clock
        self.failures = 0
        self.open_until = 0.0
        self.probing = False
        self.epoch = 0
        self.lock = threading.Lock()

    def call(self, operation):
        with self.lock:
            if self.open_until:
                if self.clock() < self.open_until or self.probing:
                    raise CircuitOpen("Provider unavailable")
                self.probing = True
            epoch = self.epoch
        try:
            result = operation()
        except Exception:
            with self.lock:
                if epoch == self.epoch:
                    self.probing = False
                    self.failures += 1
                    if self.failures >= self.threshold:
                        self.open_until = self.clock() + self.recovery_seconds
                        self.epoch += 1
            raise
        with self.lock:
            if epoch == self.epoch:
                self.probing = False
                self.failures = 0
                self.open_until = 0.0
        return result
