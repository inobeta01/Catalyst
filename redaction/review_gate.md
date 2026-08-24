# Review Gate — Pre-Commit Checklist

Each fixture in `corpus/sanitized/` must pass this checklist before committing:

## 1. PII Redaction
- [ ] No email addresses visible
- [ ] No phone numbers visible
- [ ] No SSNs or ID numbers visible
- [ ] No credit card numbers visible
- [ ] No company names or domains without anonymization

## 2. Context Preservation
- [ ] Semantic meaning of the issue is preserved
- [ ] Code structure and patterns are intact
- [ ] Error types and failure modes are unchanged

## 3. Test Credential Safety
- [ ] Only test-scope API keys referenced
- [ ] No real production URLs or endpoints
- [ ] External service identifiers are anonymized

## Sign-off
- **Reviewed by**: ___________________
- **Date**: ___________________
- **Hash**: `___________________  (SHA of redacted file)`
