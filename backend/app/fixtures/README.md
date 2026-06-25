# Market snapshot fixtures

This directory contains sanitized operational snapshots that can be committed to
GitHub and imported into a fresh environment.

The snapshot intentionally excludes runtime secrets, account passwords, API
keys, DingTalk tokens, uploaded report HTML, local database files, and full
third-party article bodies. It keeps crawler source configuration, keywords,
schedule settings, structured market signals, evidence records, intelligence
events, and opportunity leads.

Use:

```bash
PYTHONPATH=backend python3 backend/scripts/import_market_snapshot.py
```

