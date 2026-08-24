'''mcp.py - Minimal Common MCP (Message/Cache Platform) for Catalyst agents

This module provides a lightweight, file‑based cache that all three agents (triage,
code_review, brief_writer) can use to share intermediate results for the duration
of a single orchestrated task.  The design goal is simplicity and zero external
dependencies – the cache lives under the repository root in ``.mcp_cache`` and is
automatically cleaned up when the task completes.

Typical usage pattern::

    from workload.tools.mcp import MCP

    # Acquire a cache scoped to a specific orchestration run (e.g. a UUID)
    cache = MCP(task_id="${RUN_ID}")

    # Store a value produced by one agent
    cache.set("triage", result)

    # Later, another agent can retrieve it
    payload = cache.get("triage")

The cache stores JSON‑serialisable objects on disk; non‑serialisable values raise a
``TypeError`` so callers know to serialize beforehand.

The implementation deliberately avoids any network services (Redis, Memcached, …)
so it works in the constrained execution environment of Claude Code.  It is
thread‑safe for the typical single‑process orchestration model used by the
project – concurrency is handled at the orchestration level, not inside the
cache.
'''  # noqa: E501

import json
import re
import shlex
import os
import pathlib
import threading
from typing import Any, Optional


class MCPError(RuntimeError):
    """Base exception for MCP related failures."""


class MCP:
    """Minimal Common MCP cache.

    Parameters
    ----------
    task_id: str
        Identifier for the orchestrated task (e.g. a UUID). All keys are namespaced
        under this ID so concurrent runs do not interfere with each other.
    root_dir: str | pathlib.Path, optional
        Directory where the cache is stored. Defaults to ``.mcp_cache`` in the
        repository root.
    """

    _global_lock = threading.Lock()

    def __init__(self, task_id: str, root_dir: Optional[os.PathLike] = None):
        if not task_id:
            raise MCPError("task_id must be a non‑empty string")
        self.task_id = str(task_id)
        self.root = pathlib.Path(root_dir) if root_dir else pathlib.Path(".mcp_cache")
        self.task_dir = self.root / self.task_id
        # Ensure the directory hierarchy exists – this is safe to call multiple
        # times thanks to ``exist_ok=True``.
        self.task_dir.mkdir(parents=True, exist_ok=True)

    # ---------------------------------------------------------------------
    # Internal helpers
    # ---------------------------------------------------------------------
    def _key_path(self, key: str) -> pathlib.Path:
        if not key:
            raise MCPError("cache key must be a non‑empty string")
        # Sanitize the key for filesystem safety – replace path separators with
        # underscores and ensure the filename ends with .json.
        safe_key = key.replace(os.sep, "_")
        return self.task_dir / f"{safe_key}.json"

    # ---------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------
    def set(self, key: str, value: Any) -> None:
        """Store ``value`` under ``key``.

        The value must be JSON‑serialisable.  The operation is atomic – the file
        is written to a temporary location and then ``os.replace`` is used to
        move it into place.
        """
        path = self._key_path(key)
        tmp_path = path.with_suffix('.tmp')
        try:
            data = json.dumps(value, ensure_ascii=False, indent=2)
        except (TypeError, ValueError) as exc:
            raise MCPError(f"value for key '{key}' is not JSON serialisable") from exc
        # Write under lock to avoid race conditions if multiple threads try to
        # write the same key simultaneously.
        with self._global_lock, open(tmp_path, "w", encoding="utf-8") as f:
            f.write(data)
        os.replace(tmp_path, path)

    # ---------------------------------------------------------------------
    # File system utilities (extended MCP functionality)
    # ---------------------------------------------------------------------
    def read_file(self, file_path: str) -> str:
        """Read the entire contents of *file_path*.

        ``file_path`` is interpreted relative to the repository root.
        Returns the file contents as a string.  Raises ``MCPError`` if the file
        does not exist or cannot be read.
        """
        p = pathlib.Path(file_path)
        try:
            return p.read_text(encoding="utf-8")
        except Exception as exc:
            raise MCPError(f"cannot read file '{file_path}'") from exc

    def write_file(self, file_path: str, content: str) -> None:
        """Overwrite *file_path* with *content* (creates parent directories)."""
        p = pathlib.Path(file_path)
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
        except Exception as exc:
            raise MCPError(f"cannot write file '{file_path}'") from exc

    def create_file(self, file_path: str, content: str = "") -> None:
        """Create a new file at *file_path* with *content*.

        Fails with ``MCPError`` if the file already exists.
        """
        p = pathlib.Path(file_path)
        if p.exists():
            raise MCPError(f"file '{file_path}' already exists")
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
        except Exception as exc:
            raise MCPError(f"cannot create file '{file_path}'") from exc

    def delete_file(self, file_path: str) -> None:
        """Delete *file_path* if it exists.  Silently succeeds if missing."""
        p = pathlib.Path(file_path)
        try:
            p.unlink()
        except FileNotFoundError:
            pass
        except Exception as exc:
            raise MCPError(f"cannot delete file '{file_path}'") from exc

    def list_directory(self, dir_path: str) -> list[str]:
        """Return a list of entries (files and sub‑directories) in *dir_path*."""
        p = pathlib.Path(dir_path)
        if not p.is_dir():
            raise MCPError(f"'{dir_path}' is not a directory")
        return [str(child) for child in p.iterdir()]

    def move_file(self, src: str, dst: str) -> None:
        """Rename or relocate a file from *src* to *dst* (creates parents as needed)."""
        src_path = pathlib.Path(src)
        dst_path = pathlib.Path(dst)
        if not src_path.exists():
            raise MCPError(f"source file '{src}' does not exist")
        try:
            dst_path.parent.mkdir(parents=True, exist_ok=True)
            src_path.rename(dst_path)
        except Exception as exc:
            raise MCPError(f"cannot move '{src}' to '{dst}'") from exc

    def search_files(self, pattern: str, root: str = ".") -> list[str]:
        """Find files matching *pattern* under *root*.

        ``pattern`` can contain glob wildcards accepted by ``Path.rglob``.
        Returns a list of matching file paths (as strings).
        """
        base = pathlib.Path(root)
        return [str(p) for p in base.rglob(pattern) if p.is_file()]

    def grep_codebase(self, regex: str, root: str = ".") -> list[dict]:
        """Search all files under *root* for *regex*.

        Returns a list of dictionaries ``{"file": path, "line": lineno, "match": text}``.
        """
        import re
        compiled = re.compile(regex)
        results = []
        for path in pathlib.Path(root).rglob("*"):
            if path.is_file():
                try:
                    text = path.read_text(encoding="utf-8")
                except Exception:
                    continue
                for i, line in enumerate(text.splitlines(), start=1):
                    if compiled.search(line):
                        results.append({"file": str(path), "line": i, "match": line})
        return results

    def get_symbol_definition(self, symbol: str, root: str = ".") -> list[dict]:
        """Find definitions of a Python *symbol* (function, class, variable).

        Currently a simple heuristic that looks for ``def`` or ``class`` statements.
        Returns a list of location dictionaries.
        """
        pattern = rf"^(def|class)\s+{re.escape(symbol)}\b"
        return self.grep_codebase(pattern, root)

    def get_symbol_references(self, symbol: str, root: str = ".") -> list[dict]:
        """Find all usages of *symbol* across the codebase (word‑boundary match)."""
        pattern = rf"\\b{re.escape(symbol)}\\b"
        return self.grep_codebase(pattern, root)

    def get_file_outline(self, file_path: str) -> dict:
        """Return a high‑level outline of a Python file.

        The outline includes imports, class names, and function names.
        """
        p = pathlib.Path(file_path)
        if not p.is_file():
            raise MCPError(f"'{file_path}' is not a file")
        try:
            source = p.read_text(encoding="utf-8")
            import ast
            tree = ast.parse(source)
            outline = {"imports": [], "classes": [], "functions": []}
            for node in ast.iter_child_nodes(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        outline["imports"].append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    mod = node.module or ""
                    for alias in node.names:
                        outline["imports"].append(f"{mod}.{alias.name}")
                elif isinstance(node, ast.ClassDef):
                    outline["classes"].append(node.name)
                elif isinstance(node, ast.FunctionDef):
                    outline["functions"].append(node.name)
            return outline
        except Exception as exc:
            raise MCPError(f"cannot parse outline for '{file_path}'") from exc

    # ---------------------------------------------------------------------
    # Git utilities
    # ---------------------------------------------------------------------
    def _run_git(self, *args: str) -> str:
        """Execute a git command and return its stdout (raises ``MCPError`` on failure)."""
        import subprocess
        try:
            result = subprocess.run(["git", *args], cwd=str(pathlib.Path('.')),
                                    capture_output=True, text=True, check=True)
            return result.stdout.strip()
        except subprocess.CalledProcessError as exc:
            raise MCPError(f"git {' '.join(args)} failed: {exc.stderr.strip()}") from exc

    def git_status(self) -> str:
        return self._run_git("status", "--porcelain")

    def git_diff(self, staged: bool = False) -> str:
        return self._run_git("diff", "--cached" if staged else "")

    def git_log(self, n: int = 10) -> str:
        return self._run_git("log", f"-n{n}", "--pretty=short")

    def git_blame(self, file_path: str) -> str:
        return self._run_git("blame", file_path)

    def git_show(self, rev: str, path: str | None = None) -> str:
        args = ["show", rev]
        if path:
            args.append(path)
        return self._run_git(*args)

    def git_branch(self, list_branches: bool = True, switch_to: str | None = None) -> str:
        if switch_to:
            return self._run_git("checkout", switch_to)
        if list_branches:
            return self._run_git("branch", "--list")
        return ""

    def git_add(self, *paths: str) -> str:
        return self._run_git("add", *paths)

    def git_commit(self, message: str) -> str:
        # Stage all changes then commit
        self._run_git("add", ".")
        return self._run_git("commit", "-m", message)

    # ---------------------------------------------------------------------
    # Execution utilities
    # ---------------------------------------------------------------------
    def run_command(self, command: str) -> str:
        """Run *command* in a subprocess and return its stdout.

        The command is executed with the repository root as cwd.
        """
        import subprocess, shlex
        try:
            result = subprocess.run(shlex.split(command), cwd=str(pathlib.Path('.')),
                                    capture_output=True, text=True, check=True)
            return result.stdout.strip()
        except subprocess.CalledProcessError as exc:
            raise MCPError(f"command '{command}' failed: {exc.stderr.strip()}") from exc

    def run_tests(self, pattern: str | None = None) -> str:
        cmd = "pytest"
        if pattern:
            cmd += f" {shlex.quote(pattern)}"
        return self.run_command(cmd)

    def run_linter(self, target: str = ".") -> str:
        # Prefer ruff if available, otherwise fallback to flake8.
        for linter in ["ruff", "flake8"]:
            try:
                return self.run_command(f"{linter} {shlex.quote(target)}")
            except MCPError:
                continue
        raise MCPError("no known linter (ruff/flake8) installed")

    def run_type_checker(self, target: str = ".") -> str:
        # Use mypy if present.
        try:
            return self.run_command(f"mypy {shlex.quote(target)}")
        except MCPError as exc:
            raise MCPError("type checker (mypy) not available or failed") from exc

    def install_dependency(self, package: str) -> str:
        return self.run_command(f"pip install {shlex.quote(package)}")

    # ---------------------------------------------------------------------
    # Code intelligence placeholders (lightweight implementations)
    # ---------------------------------------------------------------------
    def get_diagnostics(self, file_path: str) -> str:
        """Run a simple static analysis (flake8) on *file_path* and return output."""
        return self.run_linter(file_path)

    def get_hover_info(self, file_path: str, line: int, column: int) -> str:
        """Return hover information using ``jedi`` for Python files.

        If ``jedi`` is not available, returns an empty string.
        """
        try:
            import jedi
            source = pathlib.Path(file_path).read_text(encoding="utf-8")
            script = jedi.Script(source, path=file_path)
            info = script.help(line, column)
            return info or ""
        except Exception:
            return ""

    def format_file(self, file_path: str) -> str:
        """Run ``black`` on a Python file and return the formatted source."""
        try:
            return self.run_command(f"black {shlex.quote(file_path)}")
        except MCPError as exc:
            raise MCPError(f"formatting failed for '{file_path}'") from exc

    # ---------------------------------------------------------------------
    # Context & retrieval helpers
    # ---------------------------------------------------------------------
    def search_docs(self, query: str) -> list[str]:
        """Very naive semantic search over files in the ``docs/`` directory.

        Returns paths of files containing the query substring (case‑insensitive).
        """
        matches = []
        for p in pathlib.Path("docs").rglob("*.*"):
            if p.is_file():
                try:
                    if query.lower() in p.read_text(encoding="utf-8").lower():
                        matches.append(str(p))
                except Exception:
                    continue
        return matches

    def fetch_url(self, url: str) -> str:
        """Retrieve the contents of *url* using ``requests`` (limited to plain text)."""
        import requests
        try:
            resp = requests.get(url, timeout=15)
            resp.raise_for_status()
            return resp.text
        except Exception as exc:
            raise MCPError(f"failed to fetch URL {url}") from exc

    def read_pr_diff(self, pr_id: str) -> str:
        """Fetch a PR diff using the GitHub CLI if available.

        Requires ``gh`` to be installed and authenticated.
        """
        try:
            return self.run_command(f"gh pr diff {shlex.quote(pr_id)}")
        except MCPError as exc:
            raise MCPError(f"cannot fetch diff for PR {pr_id}") from exc

    # ---------------------------------------------------------------------
    # Context manager convenience (unchanged)
    # ---------------------------------------------------------------------
    def __enter__(self) -> "MCP":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        # Clean up the task cache regardless of success/failure.  Errors during
        # cleanup are logged but not propagated to avoid masking the original
        # exception.
        try:
            self.clear()
        except Exception:
            pass


    def get(self, key: str, default: Any = None) -> Any:
        """Retrieve the value stored under ``key``.

        Returns ``default`` if the key does not exist.  Raises ``MCPError`` on JSON
        decode failures.
        """
        path = self._key_path(key)
        if not path.is_file():
            return default
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            raise MCPError(f"failed to read cache key '{key}'") from exc

    def exists(self, key: str) -> bool:
        """Return ``True`` if ``key`` is present in the cache."""
        return self._key_path(key).is_file()

    def delete(self, key: str) -> None:
        """Remove ``key`` from the cache.  Silently succeeds if the key is
        missing.
        """
        try:
            self._key_path(key).unlink()
        except FileNotFoundError:
            pass

    def clear(self) -> None:
        """Delete **all** entries for the current ``task_id``.

        The method removes the task directory recursively.  It is safe to call
        multiple times – missing directories are ignored.
        """
        try:
            if self.task_dir.is_dir():
                for child in self.task_dir.iterdir():
                    child.unlink()
                self.task_dir.rmdir()
        except Exception as exc:
            raise MCPError(f"failed to clear cache for task '{self.task_id}'") from exc

    # ---------------------------------------------------------------------
    # Context manager convenience
    # ---------------------------------------------------------------------
    def __enter__(self) -> "MCP":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        # Clean up the task cache regardless of success/failure.  Errors during
        # cleanup are logged but not propagated to avoid masking the original
        # exception.
        try:
            self.clear()
        except Exception:
            pass

# Example stub showing how agents could reference the cache (not executed at import)
if __name__ == "__main__":  # pragma: no cover
    import uuid
    run_id = uuid.uuid4().hex
    cache = MCP(task_id=run_id)
    cache.set("example", {"msg": "hello from triage"})
    print(cache.get("example"))
