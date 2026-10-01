"""Thin wrapper around Phoenix SDK (20.16.0+) for verdict annotations using the modern DataFrame API."""

import os
import logging
import time
import pandas as pd
from phoenix.client import Client

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
        """Write verdict using Phoenix modern log_span_annotations_dataframe API.

        Requires a DataFrame with span_id column. Falls back to warning if span doesn't exist.
        Includes a retry with a short pause to handle batch exporter timing (404 = span not yet exported).
        """
        # Build DataFrame matching Phoenix's expected schema
        df = pd.DataFrame([{
            "span_id": span_id,
            "name": eval_name,
            "annotator_kind": "CODE",
            "label": label,
            "score": score,
            "explanation": explanation,
        }])

        try:
            self._client.spans.log_span_annotations_dataframe(
                dataframe=df,
                sync=True,
            )
            logger.info("Verdict written for span %s: %s %.2f", span_id, label, score)
        except Exception as exc:
            # 404 = span not yet exported (batch processor delay)
            # Retry once after a short pause to let the exporter flush
            if "404" in str(exc):
                time.sleep(1.5)
                try:
                    self._client.spans.log_span_annotations_dataframe(
                        dataframe=df,
                        sync=True,
                    )
                    logger.info("Verdict written (retry) for span %s: %s %.2f", span_id, label, score)
                    return
                except Exception as retry_exc:
                    logger.warning("Phoenix log_evaluation retry failed for span %s: %s", span_id, retry_exc)
            # Common issues: span_id not found (404), malformed DF, server unreachable
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