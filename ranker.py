#!/usr/bin/env python3
"""Jev job ranker — config-driven template.

One profile x N job postings -> a ranked shortlist via TypeSafe's Jev API.
Offline mode: a keyword heuristic mirroring the same questions (no API key).

Quickstart:
  cp config.example.json config.json
  cp jobs/profile.example.txt jobs/profile.txt
  pip install typesafe-sdk
  export TYPESAFE_API_KEY=...   # or put it in .env
  python ranker.py              # or: python ranker.py --config my.json

Everything candidate-specific lives in config.json. The only secrets are in
.env (git-ignored). See README.md for the full config reference.
"""
import argparse
import json
import os
import pathlib
import re
import sys

STATUS_WORDS = {"and", "the", "of", "for", "a", "to", "in", "at", "with"}
CLOSED_STATUSES = {"denied", "closed", "skipped", "skip", "blocked"}
PENDING_STATUSES = {"applied", "holding"}
# Lower sorts first: actionable > awaiting reply > closed out.
STATUS_RANK = {"new": 0, "hold": 0, "unknown": 0,
               "applied": 1, "holding": 1,
               "denied": 2, "closed": 2, "skipped": 2, "skip": 2, "blocked": 2}

# Plain-language notes for the two advisory Choice questions. They are printed
# under the table and never enter the composite score. Override in config via
# config["questions"]["unstated_reality"|"rejection_reason"]["criteria"] and
# config["advisory"]["unstated_note"|"reject_note"] if you change the vocabularies.
DEFAULT_ADVISORY = {
    "rejection_reason": {
        "instructions": "The single most likely reason a strong but non-perfect "
                        "candidate is rejected from this specific process. Use the "
                        "candidate's explicit KNOWN GAPS section when judging fit. "
                        "Do not answer generically",
        "criteria": {
            "design_origination": "Posting centers on originating design/standards the candidate does not do",
            "hard_cert_or_degree": "A required certification, degree, license, or clearance the candidate lacks",
            "quota_or_revenue": "Quota-carrying or revenue-holding role",
            "adjacent_discipline": "Posting is really in an adjacent discipline with standards the candidate lacks",
            "seniority_or_band": "Seniority or compensation band mismatch",
            "interview_execution": "Credentials are adequate; the risk is how the candidate interviews",
            "no_real_gap": "No material gap; treat as genuine fit",
        },
    },
    "unstated_reality": {
        "instructions": "Pick the single biggest demand this posting implies that its "
                        "text does NOT state. Base it only on evidence in this posting. "
                        "If the posting states no hidden demand, choose nothing_significant",
        "criteria": {
            "travel_unstated": "Travel is understated or absent in the text but likely high",
            "consulting_utilization": "Consulting/utilization/billing model driving the scope",
            "24x7_criticality": "On-call, 24x7 uptime expectation, or major incident response load",
            "rapid_startup": "Expects fast ramp, immediate ownership, ambiguity tolerance",
            "influence_no_authority": "Success without formal authority or management title",
            "staffing_or_body_shop": "Staffing/body-shop model, or work through a subcontractor",
            "nothing_significant": "Nothing significant implied beyond what is written",
        },
    },
}
DEFAULT_REJECT_NOTE = {
    "design_origination": "posting wants design/standards authorship; candidate reviews and executes instead",
    "hard_cert_or_degree": "a required cert/degree/license/clearance blocks the candidate",
    "quota_or_revenue": "quota or revenue-holding role; candidate has no quota history",
    "adjacent_discipline": "really an adjacent discipline missing core standards",
    "seniority_or_band": "seniority or compensation band mismatch",
    "interview_execution": "credentials fine; risk is interview performance, not qualifications",
    "no_real_gap": "no material gap found",
}
DEFAULT_UNSTATED_NOTE = {
    "travel_unstated": "travel understated in the text",
    "consulting_utilization": "consulting/utilization billing model",
    "24x7_criticality": "24x7 uptime or on-call expectation",
    "rapid_startup": "fast ramp and ambiguity tolerance expected",
    "influence_no_authority": "needs influence without formal authority",
    "staffing_or_body_shop": "staffing/subcontract model",
    "nothing_significant": "nothing hidden beyond the text",
}


def load_env(root):
    """Read .env from the repo root without overriding exported shell vars."""
    env_path = root / ".env"
    if not env_path.exists():
        return False
    for raw in env_path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        os.environ.setdefault(key, value)
    return True


def load_config(path):
    cfg = json.loads(path.read_text())
    root = path.resolve().parent
    cfg.setdefault("profile", "jobs/profile.txt")
    cfg.setdefault("jobs_dir", "jobs")
    cfg.setdefault("status_file", "jobs/STATUS.md")
    cfg.setdefault("model", "jev-latest")
    cfg.setdefault("route_map", {})
    cfg.setdefault("core_routes", ["systems_engineer"])
    cfg.setdefault("poor_fit_routes", ["poor_fit", "sales_engineer"])
    cfg.setdefault("route_to_family", {})
    cfg.setdefault("pivot_families", {})
    cfg.setdefault("unknown_stretch_bonus", 0.25)
    cfg.setdefault("core_domain_threshold", 0.7)
    cfg.setdefault("core_customer_threshold", 0.5)
    cfg.setdefault("fit_scale", 3)
    cfg.setdefault("scoring", {})
    cfg["scoring"].setdefault("fit", 0.6)
    cfg["scoring"].setdefault("domain", 0.2)
    cfg["scoring"].setdefault("customer", 0.2)
    cfg["scoring"].setdefault("blocker_penalty", 0.5)
    cfg.setdefault("questions", {})
    cfg.setdefault("offline", {})
    # Resolve paths relative to the config file's directory.
    for k in ("profile", "jobs_dir", "status_file"):
        p = pathlib.Path(cfg[k])
        cfg[k] = p if p.is_absolute() else root / p
    cfg["_root"] = root
    return cfg


def classify_stretch(job_text, domain, cust, cfg):
    """Offline-mode family guess from JD keywords. Returns (kind, label, bonus)."""
    t = job_text.lower()
    if domain >= cfg["core_domain_threshold"] and cust >= cfg["core_customer_threshold"]:
        return "core", "core fit", 0.0
    best, best_hits = None, 0
    for name, fam in cfg["pivot_families"].items():
        hits = sum(1 for kw in fam.get("keywords", []) if kw.lower() in t)
        if hits > best_hits:
            best, best_hits = name, hits
    if best and best_hits >= 2:
        return best, f"stretch:{cfg['pivot_families'][best].get('label', best)}", \
            cfg["pivot_families"][best].get("transfer", 0.4)
    return "unknown_stretch", "stretch:unclassified", cfg["unknown_stretch_bonus"]


def kind_from_route(route, domain, cust, cfg):
    """Live-mode family assignment: trust Jev's route answer over keywords."""
    if route in cfg["poor_fit_routes"]:
        return "poor_fit", "stretch:poor-fit route", 0.0
    if domain >= cfg["core_domain_threshold"] and cust >= cfg["core_customer_threshold"]:
        return "core", "core fit", 0.0
    if route in cfg["core_routes"]:
        return "core", "core fit", 0.0
    fam = cfg["route_to_family"].get(route)
    if fam and fam in cfg["pivot_families"]:
        return fam, f"stretch:{cfg['pivot_families'][fam].get('label', fam)}", \
            cfg["pivot_families"][fam].get("transfer", 0.4)
    return "unknown_stretch", "stretch:unclassified", cfg["unknown_stretch_bonus"]


def stretch_adj(transferable, bonus, gap):
    return round(transferable * bonus * (1.0 - 0.5 * gap), 3)


def jev_live(profile, job_text, cfg):
    """One Jev call per posting, all questions in parallel. Matches the TypeSafe quickstart."""
    from typesafe_sdk import Choice, Noul, Score, TypeSafeClient
    q = cfg["questions"]
    adv = DEFAULT_ADVISORY
    route_q = q["route"]
    unstated_q = q.get("unstated_reality", adv["unstated_reality"])
    reject_q = q.get("rejection_reason", adv["rejection_reason"])

    client = TypeSafeClient()
    resp = client.system_one(
        state={"profile": profile, "job_posting": job_text},
        questions={
            "route": Choice(instructions=route_q["instructions"], criteria=route_q["criteria"]),
            "fit": Score(instructions=q.get("fit", {}).get(
                "instructions", "Overall fit of profile to posting"),
                criteria=q.get("fit", {}).get(
                    "criteria", ["No fit - skip", "Partial - stretch",
                                 "Strong - apply", "Bullseye - top priority"])),
            "domain_match": Noul(instructions=q["domain"]["instructions"]),
            "customer_face": Noul(instructions=q["customer_face"]["instructions"]),
            "blocker": Noul(instructions=q["blocker"]["instructions"]),
            "transferable": Noul(instructions=q["transferable"]["instructions"]),
            "stretch_gap": Noul(instructions=q["stretch_gap"]["instructions"]),
            "unstated_reality": Choice(instructions=unstated_q["instructions"],
                                       criteria=unstated_q["criteria"]),
            "rejection_reason": Choice(instructions=reject_q["instructions"],
                                       criteria=reject_q["criteria"]),
        },
        model=cfg["model"],
    )
    a = resp.answers
    fit = float(a["fit"].score)
    transferable = float(a["transferable"].noul)
    gap = float(a["stretch_gap"].noul)
    scale = cfg["fit_scale"]
    domain, cust, blocker = (float(a["domain_match"].noul),
                             float(a["customer_face"].noul),
                             float(a["blocker"].noul))
    kind, label, bonus = kind_from_route(a["route"].choice, domain, cust, cfg)
    adj = 0.0 if kind == "core" else stretch_adj(transferable, bonus, gap)
    s = cfg["scoring"]
    score = fit / scale * s["fit"] + domain * s["domain"] + cust * s["customer"] \
        - blocker * s["blocker_penalty"] + adj
    return {"route": a["route"].choice, "fit": fit, "domain": domain, "cust": cust,
            "blocker": blocker, "transfer": transferable, "gap": gap,
            "unstated": a["unstated_reality"].choice,
            "reject": a["rejection_reason"].choice,
            "kind": kind, "label": label,
            "conf": float(a["fit"].confidence),
            "score": round(max(0, score), 3), "live": True}


def jev_offline(profile, job_text, cfg):
    """Keyword mirror of the same questions. No API key required."""
    t = job_text.lower()
    off = cfg["offline"]

    def has(*ws):
        return any(w in t for w in ws)

    domain = 0.9 if has(*off.get("domain_keywords", [])) else 0.4
    cust = 0.9 if has(*off.get("customer_keywords", [])) else 0.5
    cert_req = any(c in t for c in off.get("hard_cert_terms", ["cissp"])) and \
        "preferred" not in t
    if has("quota") and has(*off.get("quota_saas_terms", ["saas", "meddpicc", "carried"])):
        blocker = 0.85
    elif has(*off.get("strong_blocker_terms", ["big-4", "utilization"])) or cert_req:
        blocker = 0.6
    elif has("clearance") and not has("no clearance"):
        blocker = 0.4
    else:
        blocker = 0.1
    if domain > 0.8 and cust > 0.8 and blocker < 0.3:
        fit = 3.0
    elif domain > 0.6 and blocker < 0.6:
        fit = 2.0
    elif domain > 0.4:
        fit = 1.0
    else:
        fit = 0.0
    route = off.get("default_route", (cfg["core_routes"] or ["systems_engineer"])[0])
    for kw, r in off.get("route_rules", []):
        if kw.lower() in t:
            route = r
            break
    if blocker > 0.7 and has("quota"):
        route = "poor_fit"
    kind, label, bonus = classify_stretch(job_text, domain, cust, cfg)
    transfer = 0.75 if kind == "core" else (0.5 if kind != "unknown_stretch" else 0.35)
    gap = 0.3 if kind == "core" else 0.6
    adj = 0.0 if kind == "core" else stretch_adj(transfer, bonus, gap)
    s = cfg["scoring"]
    score = fit / cfg["fit_scale"] * s["fit"] + domain * s["domain"] + cust * s["customer"] \
        - blocker * s["blocker_penalty"] + adj
    conf = 0.82 if abs(score - 0.5) > 0.25 else 0.58
    return {"route": route, "fit": fit, "domain": domain, "cust": cust, "blocker": blocker,
            "transfer": transfer, "gap": gap, "kind": kind, "label": label,
            "conf": conf, "score": round(max(0, score), 3), "live": False,
            "unstated": "nothing_significant", "reject": "no_real_gap"}


def recommend(score, conf, kind):
    """Stretch-tolerant action mapping. Tweak if you want a stricter bar."""
    if score >= 0.6 and conf >= 0.6:
        return "APPLY"
    if 0.4 <= score < 0.6:
        return "REVIEW-stretch" if kind != "core" else "REVIEW"
    if score < 0.4 and conf >= 0.85:
        return "SKIP"
    return "STRETCH?"


def load_status(status_path):
    if not status_path or not pathlib.Path(status_path).exists():
        return []
    rows = []
    for line in pathlib.Path(status_path).read_text().splitlines():
        if not line.startswith("|") or "---" in line or "Company" in line:
            continue
        cols = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cols) < 3:
            continue
        company, role, status = cols[0], cols[1], cols[2].lower()
        words = re.findall(r"[a-z0-9]+", company.lower())
        if not words:
            continue
        toks = {w for w in re.findall(r"[a-z0-9]+", role.lower()) if w not in STATUS_WORDS}
        rows.append((words[0], toks, role, status))
    return rows


def match_status(stem, status_rows):
    if not status_rows:
        return None
    s_toks = set(re.findall(r"[a-z0-9]+", stem.lower()))
    best_status, best_overlap = None, 0
    for key, toks, _role, status in status_rows:
        if not stem.lower().startswith(key):
            continue
        overlap = len(s_toks & toks)
        if overlap > best_overlap:
            best_status, best_overlap = status, overlap
    return best_status if best_overlap >= 2 else None


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default="config.json",
                    help="Path to config.json (default: ./config.json)")
    args = ap.parse_args()

    cfg_path = pathlib.Path(args.config)
    if not cfg_path.exists():
        sys.exit(f"Missing {cfg_path}. Copy config.example.json to config.json and edit it.")
    cfg = load_config(cfg_path)
    root = cfg["_root"]

    PROFILE_PATH = pathlib.Path(cfg["profile"])
    if not PROFILE_PATH.exists():
        sys.exit(f"Missing {PROFILE_PATH}. Copy jobs/profile.example.txt and fill it in.")
    profile = PROFILE_PATH.read_text()

    had_env = load_env(root)
    use_live = bool(os.getenv("TYPESAFE_API_KEY"))
    try:
        if use_live:
            import typesafe_sdk  # noqa: F401
    except ImportError:
        print("typesafe-sdk not installed -> offline mode. "
              "pip install typesafe-sdk and export TYPESAFE_API_KEY for live Jev.\n")
        use_live = False
    if not use_live and had_env:
        print("No TYPESAFE_API_KEY in .env or shell env -> offline mirror.\n")
    elif use_live:
        print("TYPESAFE_API_KEY found (shell or .env)\n")

    jobs_dir = pathlib.Path(cfg["jobs_dir"])
    rows = []
    status_rows = load_status(cfg["status_file"])
    for f in sorted(jobs_dir.glob("*.txt")):
        if f.name.endswith(".example.txt") or f.stem == "profile":
            continue
        job = f.read_text()
        r = jev_live(profile, job, cfg) if use_live else jev_offline(profile, job, cfg)
        key = next((k for k in cfg["route_map"] if k in f.stem), f.stem)
        r["status"] = match_status(f.stem, status_rows) or "unknown"
        rows.append((f.stem, cfg["route_map"].get(key, "-"), r))
    rows.sort(key=lambda x: (STATUS_RANK.get(x[2]["status"], 0), -x[2]["score"]))

    mode = "LIVE Jev" if rows and rows[0][2]["live"] else "OFFLINE mirror (same questions, no API)"
    print(f"Mode: {mode}\n")
    print(f"{'posting':38} {'score':>5} {'fit':>3} {'dom':>4} {'cus':>4} {'blk':>4} "
          f"{'xfer':>4} {'conf':>4} {'status':>8}  {'route':22} action")
    for name, _folder, r in rows:
        act = recommend(r["score"], r["conf"], r["kind"])
        if r["status"] in CLOSED_STATUSES:
            act = "CLOSED"
        elif r["status"] in PENDING_STATUSES:
            act = "AWAITING"
        print(f"{name[:38]:38} {r['score']:>5} {r['fit']:>3} {r['domain']:>4} {r['cust']:>4} "
              f"{r['blocker']:>4} {r['transfer']:>4} {r['conf']:>4} {r['status'][:8]:>8}  "
              f"{r['route'][:22]:22} {act} ({r['label']})")

    if status_rows:
        n_act = sum(1 for _n, _f, r in rows if r["status"] not in CLOSED_STATUSES | PENDING_STATUSES)
        n_await = sum(1 for _n, _f, r in rows if r["status"] in PENDING_STATUSES)
        n_closed = sum(1 for _n, _f, r in rows if r["status"] in CLOSED_STATUSES)
        print(f"\n{n_act} actionable, {n_await} awaiting reply, {n_closed} closed/skipped/blocked")

    s = cfg["scoring"]
    print(f"Composite: fit*{s['fit']} + domain*{s['domain']} + customer*{s['customer']} "
          f"- blocker*{s['blocker_penalty']} + stretch_adj")
    print("stretch_adj = transfer * family_bonus * (1 - 0.5*gap); core fits get 0.")
    print("Action: >=0.6 & conf>=0.6 APPLY | 0.4-0.6 REVIEW | <0.4 & conf>=0.85 SKIP | else STRETCH?")

    advisory = cfg.get("advisory", {})
    reject_note = advisory.get("reject_note", DEFAULT_REJECT_NOTE)
    unstated_note = advisory.get("unstated_note", DEFAULT_UNSTATED_NOTE)
    if rows and "reject" in rows[0][2]:
        print("\nADVISORY (not scored) — hidden demand, then likely rejection reason:")
        for name, _folder, r in rows:
            print(f"  {name[:36]:36} {reject_note.get(r['reject'], r['reject'])}")
            print(f"  {'':36} hidden: {unstated_note.get(r['unstated'], r['unstated'])}")

    if not rows:
        print("No postings found. Add jobs/<company>_<role>.txt files and re-run.")


if __name__ == "__main__":
    main()
