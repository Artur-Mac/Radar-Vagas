"""Base connector interface for Radar-Vagas PoC."""

import hashlib
from abc import ABC, abstractmethod
from collections.abc import Sequence
from itertools import zip_longest

from poc.schema import CanonicalJob, RawJobRecord


def balanced_sample[T](groups: Sequence[Sequence[T]], limit: int) -> list[T]:
    """Interleave source groups so the first large group cannot consume the sample."""
    if limit <= 0:
        return []

    sampled: list[T] = []
    for row in zip_longest(*groups):
        for item in row:
            if item is not None:
                sampled.append(item)
                if len(sampled) == limit:
                    return sampled
    return sampled


class BaseConnector(ABC):
    """Abstract base class for job source connectors."""

    def __init__(self, source_name: str):
        self.source_name = source_name

    @abstractmethod
    def fetch_jobs(self, limit: int = 100) -> list[RawJobRecord]:
        """Fetch raw job records from source."""

    @abstractmethod
    def normalize(self, raw_record: RawJobRecord) -> CanonicalJob:
        """Transform raw job record into canonical job schema."""

    def compute_hash(self, content: str) -> str:
        """Compute SHA256 content hash."""
        return hashlib.sha256(content.encode("utf-8")).hexdigest()
