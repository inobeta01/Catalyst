"""Stage 4 — verdict annotation transport roundtrip.

Round-trips a single SpanAnnotation through Phoenix using the SDK's
log_span_annotations / get_span_annotations path.
"""
import os
import pandas as pd

from phoenix.client import Client
from phoenix.client.resources.spans import SpanAnnotationData


def test_eval_roundtrip() -> None:
    endpoint = os.environ.get("PHOENIX_HOST", "http://localhost:6006")
    client = Client(base_url=endpoint)

    span_id = "dummy-span-id-1"
    annotation_name = "drift_detection"

    # 1. Log the verdict annotation using log_span_annotations
    print(f"Logging annotation on span={span_id}…")
    annotations = [
        SpanAnnotationData(
            span_id=span_id,
            name=annotation_name,
            annotator_kind="CODE",
            result={
                "label": "pass",
                "score": 0.95,
                "explanation": "Drift within bounds"
            },
        )
    ]

    client.spans.log_span_annotations(
        span_annotations=annotations,
        sync=True,
    )

    # 2. Read it back via the get_span_annotations_dataframe API
    print("Reading annotations back…")
    df = client.spans.get_span_annotations_dataframe(
        span_ids=[span_id],
        project_identifier="default",
        include_annotation_names=[annotation_name],
    )
    print(df)
    assert len(df) > 0, "No annotations retrieved"
    print("Round-trip OK")


if __name__ == "__main__":
    test_eval_roundtrip()