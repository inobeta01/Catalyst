# Replay Cache

Recorded real tool responses, keyed by input hash. Committed to ensure
deterministic control runs. Format: `<sha256(input_hash)>.json`.

Regenerate with:
```bash
catalyst reset --replay-cache
```
