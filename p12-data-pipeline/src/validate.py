"""
p12 — Record validation.

Checks each extracted record against a set of quality rules before it
enters the feature store. Rejected records are logged with a reason —
they are never silently dropped.

Rules:
  - PMID must be present and numeric
  - Abstract must be present and at least 50 characters
  - Publication date must be parseable
  - No duplicate PMIDs within the same batch
"""

import logging
import re
from dataclasses import dataclass, field

log = logging.getLogger("p12.validate")


@dataclass
class ValidationResult:
    accepted: list[dict] = field(default_factory=list)
    rejected: list[dict] = field(default_factory=list)

    @property
    def acceptance_rate(self) -> float:
        total = len(self.accepted) + len(self.rejected)
        return len(self.accepted) / total if total > 0 else 0.0


def validate(records: list[dict]) -> ValidationResult:
    """
    Validate a batch of extracted records.

    Returns a ValidationResult with accepted and rejected records.
    Rejected records include a '_rejection_reason' key.
    """
    result = ValidationResult()
    seen_pmids: set[str] = set()

    for record in records:
        reason = _check(record, seen_pmids)
        if reason:
            log.warning("record_rejected", extra={"pmid": record.get("pmid"), "reason": reason})
            result.rejected.append({**record, "_rejection_reason": reason})
        else:
            seen_pmids.add(record["pmid"])
            result.accepted.append(record)

    log.info(
        "validation_complete",
        extra={
            "accepted": len(result.accepted),
            "rejected": len(result.rejected),
            "acceptance_rate": round(result.acceptance_rate, 3),
        },
    )
    return result


def _check(record: dict, seen_pmids: set[str]) -> str | None:
    """Return a rejection reason string, or None if the record is valid."""
    pmid = record.get("pmid", "")
    if not pmid or not re.match(r"^\d+$", str(pmid)):
        return "missing or non-numeric PMID"

    if pmid in seen_pmids:
        return f"duplicate PMID {pmid} in batch"

    abstract = record.get("abstract", "")
    if not abstract or len(abstract.strip()) < 50:
        return f"abstract missing or too short ({len(abstract)} chars)"

    pubdate = record.get("pubdate", "")
    if not pubdate or not re.search(r"\d{4}", pubdate):
        return "missing or unparseable publication date"

    return None
