"""Sandbox wiring: E2B / Docker runtime configuration."""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class SandboxConfig:
    sandbox_type: str = os.getenv("SANDBOX_TYPE", "docker")  # docker or e2b
    api_key: Optional[str] = os.getenv("SANDBOX_API_KEY")
    base_url: str = os.getenv("SANDBOX_BASE_URL", "http://localhost:8080")
    timeout_seconds: int = int(os.getenv("SANDBOX_TIMEOUT", "120"))

    def is_remote(self) -> bool:
        return self.sandbox_type == "e2b"
