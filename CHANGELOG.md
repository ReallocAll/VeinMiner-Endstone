# Changelog

## Unreleased — server specialization (incomplete, safety-gated)

- Replaced the legacy command, statistics, MySQL, update checker and destructive mining code with a small pure-Python settings and GUI implementation.
- Added five UUID-keyed, persistent personal options with conservative defaults.
- Added Chinese ActionForm and non-OP `/vm` / `/veinminer` access.
- Removed unverified synthetic mining and manual reward paths rather than risking Territory protection or Tianyan audit bypass.
- Documented missing public block authorization, auditing, and vanilla mining APIs. **Mining is not yet operational**.
- Added focused unit tests and minimal lint / wheel CI.
