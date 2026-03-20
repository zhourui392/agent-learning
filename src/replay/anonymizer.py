"""Chain-based traffic anonymizer -- strips PII before replay."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple


# (pattern, replacement_label)
_DEFAULT_PATTERNS: List[Tuple[str, str]] = [
    (r"\b1[3-9]\d{9}\b", "<PHONE>"),
    (r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", "<EMAIL>"),
    (r"\b\d{15,18}[Xx]?\b", "<ID_CARD>"),
    (r"\b[\u4e00-\u9fff]{2,4}\b", "<NAME>"),
]


class TrafficAnonymizer:
    """Regex-chain anonymizer for replay records.

    Parameters
    ----------
    patterns : list of (regex, replacement) pairs, optional
        Custom anonymization rules.  Defaults to phone/email/id/name.
    """

    def __init__(
        self,
        patterns: List[Tuple[str, str]] | None = None,
    ) -> None:
        raw = patterns if patterns is not None else _DEFAULT_PATTERNS
        self._rules = [(re.compile(p), r) for p, r in raw]

    def anonymize_text(self, text: str) -> str:
        """Apply all rules to a text string."""
        result = text
        for pattern, replacement in self._rules:
            result = pattern.sub(replacement, result)
        return result

    def anonymize_record(self, record_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Deep-walk a record dict and anonymize all string values."""
        return self._walk(record_dict)  # type: ignore[return-value]

    def _walk(self, obj: Any) -> Any:
        if isinstance(obj, str):
            return self.anonymize_text(obj)
        if isinstance(obj, dict):
            return {k: self._walk(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [self._walk(item) for item in obj]
        return obj
