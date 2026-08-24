"""Redaction pipeline: applies PII redaction (presidio or equivalent) to raw corpus data."""

import re
import hashlib
from pathlib import Path
from typing import List, Dict, Tuple


class RedactionPipeline:
    """Apply redaction rules to raw data and output to sanitized/."""

    def __init__(self, rules_dir: str = "redaction/rules"):
        self.rules_dir = Path(rules_dir)
        self.patterns: List[Tuple[str, str]] = []  # (name, regex)
        self._load_rules()

    def _load_rules(self):
        """Load PII patterns from rules directory."""
        # Default patterns if no rule files exist
        defaults = {
            "email": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
            "phone": r"\b\d{3}-\d{3}-\d{4}\b",
            "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
            "credit_card": r"\b(?:\d[ -]*?){13,16}\b",
        }
        for name, pattern in defaults.items():
            self.patterns.append((name, pattern))

    def redact(self, text: str) -> str:
        """Apply all redaction patterns to text."""
        result = text
        for name, pattern in self.patterns:
            result = re.sub(pattern, f"[REDACTED-{name.upper()}]", result)
        return result

    def process_file(self, raw_path: Path, out_path: Path):
        """Read raw file, redact, write to sanitized path."""
        content = raw_path.read_text()
        redacted = self.redact(content)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(redacted)

    def process_corpus(self, raw_dir: str = "corpus/raw", out_dir: str = "corpus/sanitized"):
        """Process all files in raw/ into sanitized/."""
        raw = Path(raw_dir)
        out = Path(out_dir)
        for f in raw.rglob("*"):
            if f.is_file():
                rel = f.relative_to(raw)
                # Determine subdirectory from first path component (e.g., triage/)
                category = rel.parts[0] if len(rel.parts) > 1 else "misc"
                dest = out / category / rel.name
                self.process_file(f, dest)
