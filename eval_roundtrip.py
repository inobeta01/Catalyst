"""Stage 4 — verdict annotation transport roundtrip.

Round-trips a single SpanAnnotation through Phoenix using the SDK's
Spans.add_span_annotation / Spans.get_span_annotations path.
"""
import os

from phoenix.client import Client


def test_eval_roundtrip() -> None:
    endpoint = os.environ.get("PHOENIX_HOST", "http://localhost:6006")
    client = Client(base_url=endpoint)

    span_id = "dummy-span-id-1"
    annotation_name = "drift_detection"

    # 1. Log the verdict annotation
    print(f"Logging annotation on span={span_id}…")
    client.spans.add_span_annotation(
        span_id=span_id,
        annotation_name=annotation_name,
        annotator_kind="CODE",
        label="pass",
        score=0.95,
        explanation="Drift within bounds",
        metadata={"mode": "pass"},
        sync=True,
    )

    # 2. Read it back via the dataframe API (always available on project "default")
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