# Jev Job Ranker (template)

Rank N job postings against one profile using [TypeSafe](https://typesafe.ai)'s
Jev model — a config-driven template you clone, personalize, and run.

One `jobs/profile.txt` × many `jobs/*.txt` postings → one table with a score,
a route label, stretch detection, an advisory "hidden demand / likely rejection
reason" readout, and an APPLY / REVIEW / SKIP action per row.

Built for the "tailoring agent + human decides" loop, and usable stand-alone.

## Quickstart

```bash
git clone <your-fork-or-template-url> jev-job-ranker
cd jev-job-ranker
python3 --version            # 3.11+ recommended (3.10 works)

cp config.example.json config.json          # edit: questions, routes, families
cp jobs/profile.example.txt jobs/profile.txt # edit: YOUR profile
cp jobs/STATUS.example.md jobs/STATUS.md     # optional pipeline tracker
cp .env.example .env                         # paste your TYPESAFE_API_KEY

pip install typesafe-sdk
# or, no key yet / offline: skip the SDK — the mirrored keyword heuristic runs

python ranker.py             # add --config path/to/config.json if elsewhere
```

Add postings as `jobs/<company>_<role>.txt` (snake_case; see
`examples/sample_posting.txt`), then re-run.

## How it works

Live mode asks Jev one combined question set per posting (route, fit score,
domain match, customer-facing demand, hard-blocker presence, transferable
skills, stretch-gap, plus two advisory questions). The composite is:

```
score = fit/scale*0.6 + domain*0.2 + customer*0.2 - blocker*0.5 + stretch_adj
stretch_adj = transfer * family_bonus * (1 - 0.5*gap)   # core fits get 0
```

Action mapping: `>=0.6 & conf>=0.6` APPLY · `0.4–0.6` REVIEW · `<0.4 & conf>=0.85`
SKIP · otherwise `STRETCH?`. Rows already in `jobs/STATUS.md` are labeled CLOSED
or AWAITING and sorted below actionable ones.

The two advisory questions (hidden demand, likely rejection reason) are printed
under the table and **never enter the score**. Treat the APPLY-vs-STRETCH? edge
as noise; the score carries more information than the label.

## Config reference (`config.json`)

| Key | Purpose |
|---|---|
| `profile`, `jobs_dir`, `status_file` | Paths (relative to config file) |
| `model` | Jev model id, e.g. `jev-latest` |
| `questions.route.criteria` | The routes Jev can pick; you define the vocabulary |
| `questions.{domain,customer_face,blocker,transferable,stretch_gap}` | Noul question instructions |
| `core_routes` / `poor_fit_routes` | Routes classed as core fit / automatic poor fit |
| `route_to_family` + `pivot_families` | Map route → stretch family; families carry `keywords` + `transfer` bonus |
| `unknown_stretch_bonus`, `core_domain_threshold`, `core_customer_threshold`, `fit_scale` | Classifier tuning |
| `scoring.{fit,domain,customer,blocker_penalty}` | Composite weights |
| `route_map` | Optional `{filename_substring: resume_folder}` shown as a column |
| `offline.*` | Keywords for the no-API mirror |
| `advisory.{reject_note,unstated_note}` | Override the printed advisory explanations |

Everything candidate-specific lives here. The code is mechanics only.

## Your profile format

Include an explicit `KNOWN GAPS AND LIMITATIONS` section. Jev reads stated
negatives; silence gets inferred. See `jobs/profile.example.txt`.

## Offline mode

No `TYPESAFE_API_KEY` or no SDK → keyword-mirror heuristic with the same output
shape. Useful for demos and CI; scores are rougher than live Jev.

## Privacy

`.gitignore` excludes `.env`, your real `config.json`, `jobs/profile.txt`,
`jobs/STATUS.md`, and real postings. The repo ships only examples with a
**fictional** persona (Job Seeker). Don't commit your pipeline. Your
`TYPESAFE_API_KEY` is a credential — Jev calls are billed to your account.

## FAQ

- **Do others need their own API key?** Yes. The SDK is MIT; the hosted Jev API
  is TypeSafe's commercial service.
- **Can I change the model?** Yes, `model` in config.
- **Is this affiliated with TypeSafe or Anthropic?** No. Independent template.
- **Python version?** 3.10+ (stdlib `tomllib` not required; config is JSON).

## License

MIT. See `LICENSE`.
