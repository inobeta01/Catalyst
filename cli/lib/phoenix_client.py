"""Thin wrapper around Phoenix SDK (20.3.0+) for verdict annotations."""

import os
import logging
import pandas as pd
from phoenix.client import Client
from phoenix.client.resources.spans import SpanAnnotationData

logger = logging.getLogger(__name__)


class VerdictTransport:

    def __init__(self, base_url: str = None, project: str = "catalyst"):
        self.base_url = base_url or os.getenv("PHOENIX_BASE_URL", "http://localhost:6006")
        self.project = project
        self._client = Client(base_url=self.base_url)

    def log_evaluation(
        self,
        span_id: str,
        eval_name: str,
        label: str,
        score: float,
        explanation: str,
    ):
        """Write verdict using Phoenix native log_span_annotations — no raw HTTP."""
        try:
            annotations = [
                SpanAnnotationData(
                    span_id=span_id,
                    name=eval_name,
                    annotator_kind="CODE",
                    result={
                        "label": label,
                        "score": score,
                        "explanation": explanation,
                    },
                )
            ]
            self._client.spans.log_span_annotations(
                span_annotations=annotations,
                sync=True,
            )
            logger.info("Verdict written for span %s: %s %.2f", span_id, label, score)
        except Exception as exc:
            logger.warning("Phoenix log_evaluation failed for span %s: %s", span_id, exc)

    def get_evaluations(self, span_id: str, eval_name: str):
        """Read back evaluations for a span."""
        try:
            df = self._client.spans.get_span_annotations_dataframe(
                span_ids=[span_id],
                project_identifier=self.project,
                include_annotation_names=[eval_name] if eval_name else None,
            )
            if df is None or df.empty:
                return None
            return df
        except Exception as exc:
            logger.warning("Phoenix get_evaluations failed for span %s: %s", span_id, exc)
            return None