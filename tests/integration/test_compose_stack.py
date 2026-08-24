"""Integration test: verify the compose stack starts and connects."""

import pytest
import time
import requests


@pytest.fixture(scope="module")
def wait_for_services():
    """Wait for Phoenix and AgentOps to be ready."""
    endpoints = [
        "http://localhost:6006",
        "http://localhost:8000",
    ]
    for url in endpoints:
        for _ in range(30):
            try:
                requests.get(url, timeout=2)
                break
            except requests.ConnectionError:
                time.sleep(1)
        else:
            pytest.fail(f"Service at {url} did not start")


def test_phoenix_available(wait_for_services):
    """Phoenix should be reachable."""
    resp = requests.get("http://localhost:6006")
    assert resp.status_code in (200, 302)


def test_agentops_available(wait_for_services):
    """AgentOps should be reachable."""
    resp = requests.get("http://localhost:8000")
    assert resp.status_code in (200, 302)
