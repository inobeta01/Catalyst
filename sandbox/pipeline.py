"""Sandbox pipeline: integrates redaction with E2B sandbox execution."""

import os
from pathlib import Path
from typing import Optional

from e2b import Sandbox
from sandbox.runtime_config import SandboxConfig
from redaction.pipeline import RedactionPipeline


class SandboxPipeline:
    """Runs redacted corpus through E2B sandbox and writes outputs."""

    def __init__(self, config: Optional[SandboxConfig] = None):
        self.config = config or SandboxConfig()
        self.redaction = RedactionPipeline()

    def run_redacted_through_sandbox(
        self,
        raw_dir: str = "corpus/raw",
        sanitized_dir: str = "corpus/sanitized",
        output_dir: str = "sandbox/output",
    ) -> Path:
        """Redact raw data, then run each sanitized file in the sandbox.

        The sandbox output is written to ``output_dir``.  The method returns the
        path to the output directory for downstream callers.
        """
        # Redact raw data first – this also populates ``self.redaction``'s map.
        self.redaction.process_corpus(raw_dir, sanitized_dir)
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        for f in Path(sanitized_dir).rglob("*"):
            if f.is_file():
                with Sandbox() as sandbox:
                    # Upload sanitized file into the sandbox's virtual FS.
                    sandbox.files.write(str(f), f.read_text())
                    # Execute a simple cat to prove the file is reachable.
                    result = sandbox.run("cat /home/user/file")
                    (out / f.name).write_text(str(result.get_stdout()))
        return out
