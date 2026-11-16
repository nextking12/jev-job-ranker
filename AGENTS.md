# AGENTS.md — Jev Ranker workflow for coding agents

Generic, candidate-neutral instructions for an agent (OpenCode, Claude Code,
Cursor, etc.) driving this repo. Copy it, then adapt the sections marked TODO.

## 1. When the user pastes a job description or URL
Save it as `jobs/<company>_<role>.txt` (lowercase, snake_case). Format:

```
<Company> - <Title>
Location: <city/remote>
Source: <URL or "pasted by user">
Salary: <if listed, else omit>

Role:
<2-4 sentence summary>

What You'll Do:
- <bullets>

Who You Are / Requirements:
- <keep hard requirements verbatim: years, certs, clearance, quota, travel>

Notes:
- <flags if present, else omit>
```

Strip boilerplate: EEO, marketing nav, social links. Keep tech keywords exactly.
If the URL fetch fails, ask the user to paste the text — never invent requirements.

## 2. Run the ranker
`python ranker.py` (add `--config path/to/config.json` if needed).
Live mode needs `TYPESAFE_API_KEY` in `.env` (see `.env.example`).

## 3. Interpret the table
- score >= 0.6 and conf >= 0.6 -> APPLY
- 0.4 <= score < 0.6 -> REVIEW (RE-TAILOR / decide yourself)
- score < 0.4 and conf >= 0.85 -> SKIP
- otherwise -> STRETCH? — surface it, let the user decide
- CLOSED / AWAITING rows are already tracked in STATUS.md; do not re-apply.

Label every stretch role with its single biggest gap (from the route + advisory
columns), and state which 2+ core strengths transfer. Never dress a stretch up
as a core fit.

## 4. Status tracking
Keep `jobs/STATUS.md` as the source of truth:
`| company | role | status(new|applied|holding|denied|closed|blocked) | date |`
Update it in the same turn the user reports a change.

## 5. Privacy
- Never commit `.env`, `config.json`, real postings, or `jobs/profile.txt`.
- Contact lines in any generated document: location + email + public links only —
  no phone number.
