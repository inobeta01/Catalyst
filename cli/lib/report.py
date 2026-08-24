"""Report: pass/fail/infra-error/noise report generator."""

from dataclasses import dataclass, field
from typing import List, Dict, Any


@dataclass
class TestResult:
    name: str
    status: str  # "pass", "fail", "infra_error", "noise"
    trace_id: str
    failure_mode: str = ""
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Report:
    results: List[TestResult] = field(default_factory=list)

    def add_result(self, result: TestResult):
        self.results.append(result)

    def summary(self) -> Dict[str, int]:
        counts = {"pass": 0, "fail": 0, "infra_error": 0, "noise": 0}
        for r in self.results:
            counts[r.status] = counts.get(r.status, 0) + 1
        return counts

    def render(self) -> str:
        lines = ["=== Catalyst Evaluation Report ==="]
        for r in self.results:
            lines.append(f"  [{r.status.upper()}] {r.name} (trace: {r.trace_id[:8]})")
            if r.failure_mode:
                lines.append(f"    → failure mode: {r.failure_mode}")
        lines.append(f"\nSummary: {self.summary()}")
        return "\n".join(lines)
