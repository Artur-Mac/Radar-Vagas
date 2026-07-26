"""Deduplication module for PoC."""

import hashlib
import re

from poc.schema import CanonicalJob


class Deduplicator:
    """Detects duplicate job postings using content hashes and title/company heuristics."""

    def __init__(self):
        self.seen_exact_hashes = set()
        self.seen_signatures = set()

    @staticmethod
    def normalize_text(text: str) -> str:
        """Strip punctuation, special chars and extra spaces."""
        text = text.lower()
        text = re.sub(r"[^\w\s]", "", text)
        return re.sub(r"\s+", " ", text).strip()

    def is_duplicate(self, job: CanonicalJob) -> tuple[bool, str]:
        """
        Check if a job is a duplicate.
        Returns (is_duplicate: bool, reason: str)
        """
        # 1. Exact description hash check
        desc_norm = self.normalize_text(job.description_clean)
        desc_hash = hashlib.md5(desc_norm.encode("utf-8")).hexdigest() if desc_norm else None

        if desc_hash and desc_hash in self.seen_exact_hashes:
            return True, "exact_description_match"

        # 2. Company + Title + Location signature check
        title_norm = self.normalize_text(job.title_normalized)
        comp_norm = self.normalize_text(job.company_normalized)
        loc_norm = self.normalize_text(job.location_raw or "")

        sig = f"{comp_norm}::{title_norm}::{loc_norm}" if comp_norm and title_norm else None
        if sig and sig in self.seen_signatures:
            return True, "signature_match"

        # Register non-duplicate
        if desc_hash:
            self.seen_exact_hashes.add(desc_hash)
        if sig:
            self.seen_signatures.add(sig)
        return False, ""
