# Jev Job Ranker

**A helper that reads job ads and tells you which ones are worth applying to.**

You paste in job postings, it scores each one against your resume/background,
and you get a shortlist: apply, review, or skip. It's not a magic replacement
for your judgment — it's a shortlist maker so you spend your time on the
postings that actually fit you.

- **Works two ways:** with an AI model from [TypeSafe](https://typesafe.ai)
  (better scores, needs a paid API key) or in offline demo mode (rough scores,
  no account needed).
- **Private by design:** your resume, postings, and API key stay on your
  computer. Nothing is uploaded anywhere except the TypeSafe AI service itself.
- **Made for AI coding agents** (OpenCode, Claude Code, Cursor…) but you can
  also drive it yourself from a terminal.

Built for job seekers, and for career coaches or agents helping them.

## What you'll need

| Thing | Why | Cost |
|---|---|---|
| A computer (Mac, Windows, or Linux) | Runs the tool | — |
| [Python](https://www.python.org/downloads/) 3.10+ (free) | The tool is a Python program | Free |
| This repository | Download it with the steps below | Free |
| A [TypeSafe](https://typesafe.ai) account + API key | Powers the AI scoring (optional) | Paid, per use |

An **API key** is like a password that lets a program use a paid AI service.
You create it in your TypeSafe account and paste it into a local file (`.env`)
that the tool reads. It never leaves your computer except to talk to TypeSafe.

> Not sure about the technical parts? The easiest path: install an AI coding
> agent (like OpenCode or Claude Code) and say
> *"Set up this repo for me and walk me through it."* The repo includes an
> `AGENTS.md` file written for exactly that.

## Setup, step by step

### 1. Get the code

Open a terminal (on macOS: the Terminal app; on Windows: Command Prompt or
PowerShell) and run:

```bash
git clone https://github.com/nextking12/jev-job-ranker.git
cd jev-job-ranker
```

(Don't have `git`? Download the repo as a ZIP from GitHub instead:
the green **Code** button → **Download ZIP**, then unzip it and open a
terminal in that folder.)

### 2. Check you have Python

```bash
python3 --version
```

You want `3.10` or newer. If you see "command not found", install Python from
python.org first, then try again.

### 3. Create your three personal files

These are the only files you edit. Copy the examples:

```bash
cp config.example.json config.json
cp jobs/profile.example.txt jobs/profile.txt
cp jobs/STATUS.example.md jobs/STATUS.md   # optional: tracks your applications
```

- **`config.json`** — tells the tool what kinds of roles you're looking for,
  what counts as a dealbreaker (clearance required, quota carrying, etc.),
  and how to weigh things. The example works out of the box for a software
  engineer; edit the parts that describe *your* situation.
- **`jobs/profile.txt`** — your background, in plain text. Replace the
  fictional "Job Seeker" example with your own experience. **Important:**
  include a section called `KNOWN GAPS AND LIMITATIONS` and list what you
  *don't* have or can't do. The AI reads stated gaps far better than silence —
  an honest list makes the scores much more accurate. (No phone number —
  location, email, and public links only.)
- **`jobs/STATUS.md`** — a simple table tracking which postings you've
  applied to, been rejected from, or are holding. The tool reads it so it
  stops recommending jobs you've already dealt with.

### 4. (Optional but recommended) Connect the AI

1. Create an account at [typesafe.ai](https://typesafe.ai) and get an API key.
2. ```bash
   cp .env.example .env
   ```
3. Open `.env` in any text editor and paste your key after `TYPESAFE_API_KEY=`.

Then:

```bash
pip install typesafe-sdk
```

If you skip this step entirely, the tool runs in **offline mode**: a simpler
keyword-based estimate with the same table output. Good for a first look; the
AI version is noticeably smarter.

### 5. Add postings and run

Save each job ad as a plain text file in `jobs/`, named
`<company>_<role>.txt`, e.g. `jobs/acme_backend_engineer.txt`
(see `examples/sample_posting.txt` for the format).

Then:

```bash
python ranker.py
```

### What the table means, column by column

| Column | Plain meaning |
|---|---|
| posting | Which job ad this row is |
| score | Overall fit, 0–1. Higher is better. Roughly: 0.6+ = apply-worthy |
| fit | How strong the match is at a glance (0–3) |
| dom | Does the role need your hands-on skills? (0–1) |
| cus | Does it need customer-facing work (discovery, demos, handoff)? (0–1) |
| blk | Dealbreaker presence — clearance, quota, etc. Lower is better |
| xfer | Do at least 2 of your strengths transfer? (0–1) |
| conf | How confident the AI is in its fit score (0–1) |
| status | From your STATUS.md: new / applied / denied / … |
| route | Which track the AI thinks fits (you define these in config.json) |
| action | **APPLY** (apply), **REVIEW** (read it and decide), **SKIP** (don't bother), **STRETCH?** (maybe — your call), plus **AWAITING** / **CLOSED** if you already dealt with it |

Two advisory notes print under the table (hidden demand, likely rejection
reason). They're **not** part of the score — they're context to help your
judgment, e.g. "this posting implies travel but never says how much."

**Rule of thumb:** trust the score more than the label; near-boundary labels
(APPLY vs STRETCH?) are coin flips.

## Advanced: customizing (`config.json`)

You don't need this to get started. When you do:

| Key | What it controls |
|---|---|
| `questions.route.criteria` | The role tracks the AI can pick from, in your words |
| `questions.{domain,customer_face,blocker,transferable,stretch_gap}` | What the AI is asked about |
| `core_routes` / `poor_fit_routes` | Tracks that count as core fit / automatic mismatch |
| `route_to_family` + `pivot_families` | Adjacent role families you'd consider, with a `transfer` bonus |
| `scoring.*` | How each factor weighs into the score |
| `offline.*` | Keywords used in offline mode |
| `advisory.*` | The explanatory notes printed under the table |

## FAQ

**Do I need to know how to code?** No. Most people can copy the fictional
example files, fill them in, and run the commands. An AI agent makes it even
easier.

**How much does the AI cost?** TypeSafe bills per use; a typical run over a
dozen postings is a handful of AI calls. See typesafe.ai for pricing.
Offline mode is free.

**Is my data private?** Your files stay local. Your profile and job postings
are sent to TypeSafe's AI to generate scores — read their privacy terms if
that matters to you. Never commit `.env` (your API key) or your real profile
to a shared copy of this repo.

**Can I change the model?** Yes — `model` in `config.json`.

**Is this affiliated with TypeSafe or Anthropic?** No. Independent project.

**License?** MIT — do what you like, no warranty. See `LICENSE`.
