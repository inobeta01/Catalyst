"""Phoenix client: read/write annotations, poll with timeout."""

import requests
import time


class PhoenixClient:
    def __init__(self, base_url: str = "http://localhost:6006"):
        self.base_url = base_url

    def get_annotations(self, trace_id: str):
        """Fetch annotations for a trace."""
        resp = requests.get(f"{self.base_url}/api/v1/traces/{trace_id}/annotations")
        return resp.json() if resp.ok else {}

    def add_annotation(self, trace_id: str, annotation: dict):
        """Add an annotation to a trace."""
        resp = requests.post(
            f"{self.base_url}/api/v1/traces/{trace_id}/annotations",
            json=annotation,
        )
        return resp.ok

    def poll_trace(self, trace_id: str, timeout: int = 60):
        """Poll for a trace until it completes or timeout."""
        start = time.time()
        while time.time() - start < timeout:
            resp = requests.get(f"{self.base_url}/api/v1/traces/{trace_id}")
            if resp.ok:
                trace = resp.json()
                if trace.get("status", {}).get("state") == "COMPLETED":
                    return trace
            time.sleep(1)
        raise TimeoutError(f"Trace {trace_id} did not complete within {timeout}s")
