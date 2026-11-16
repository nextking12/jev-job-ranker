# STATUS.md — source of truth for your pipeline
# Ranker reads this file to label rows as new / applied / holding / denied / blocked.
# First company word in the posting filename must match the Company column (case-insensitive),
# and at least 2 role tokens must overlap (stop words like "of", "the" are ignored).

| Company | Role | Status | Date |
|---|---|---|---|
| Globex | Senior Platform Engineer | applied | 2026-11-10 |
| Initech | Backend Engineer II | denied | 2026-11-08 |
