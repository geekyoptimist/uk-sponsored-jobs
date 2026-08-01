#!/usr/bin/env python3
"""One-command entry point.

    python3 scripts/run.py --title "product marketing manager"
    python3 scripts/run.py --title "product manager" --sector crypto,fintech
    python3 scripts/run.py --title "growth lead" --city london

Builds a config from the job title, runs the whole pipeline, prints a shortlist.
Uses the bundled 561-company target list unless you supply your own.
"""
import json, os, re, subprocess, sys, urllib.request, ssl

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
INSTALLED = os.path.expanduser("~/.claude/skills/visa-sponsor-job-finder")
REGISTER_PAGE = "https://www.gov.uk/government/publications/register-of-licensed-sponsors-workers"


def asset(name):
    """Find a bundled asset whether the skill is installed, cloned, or partially copied."""
    for base in (SKILL, os.getcwd(), INSTALLED):
        p = os.path.join(base, name)
        if os.path.exists(p):
            return p
    sys.exit(f"missing bundled file: {name}\n"
             f"looked in: {SKILL}, {os.getcwd()}, {INSTALLED}\n"
             f"copy the whole skill directory, not just scripts/")

# Title keyword -> (role family, SOC code, going rate). UK figures; see
# references/soc-eligibility.md and re-verify before relying on them.
FAMILIES = [
    ("partnerships_bd", r"partnership|business development|ecosystem|alliance|channel|bd\b",
     "3556 Sales accounts & business development managers", 55200, 2.6),
    ("product", r"product manager|product owner|product lead|head of product|\bpm\b",
     "2440 Business & financial project management professionals", 56500, 2.4),
    ("marketing_growth", r"marketing|growth|brand|content|demand gen|lifecycle|crm|gtm|campaign|seo|performance",
     "2432 Marketing and commercial managers", 50100, 3.0),
    ("data", r"data|analytics|business intelligence",
     "2433 Business analysts", 50000, 2.0),
]

BLOCKED_TITLE = re.compile(
    r"\bexecutive\b|\bassociate\b|\bassistant\b|\bcoordinator\b|\bspecialist\b|"
    r"\brepresentative\b|\bsdr\b|\bbdr\b", re.I)

UK_CITIES = (r"\bunited\s+kingdom\b|\bu\.?k\.?\b|\blondon\b|\bmanchester\b|\bedinburgh\b|"
             r"\bcambridge\b|\bbristol\b|\bleeds\b|\bglasgow\b|\bbirmingham\b|\boxford\b|"
             r"\breading\b|\bbelfast\b|\bcardiff\b|\bengland\b|\bscotland\b|\bwales\b|"
             r"\bbrighton\b|\bnewcastle\b|\bsheffield\b|\bnottingham\b")


def arg(name, default=None):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def classify_title(title):
    t = title.lower()
    for fam, pat, soc, rate, weight in FAMILIES:
        if re.search(pat, t):
            return fam, soc, rate, weight
    return "other", "verify the occupation code on gov.uk", 41700, 2.0


def title_to_pattern(title):
    """Broaden the title into a regex that catches sensible variants."""
    words = [w for w in re.split(r"\W+", title.lower())
             if w and w not in {"a", "an", "the", "of", "and", "for"}]
    core = [w for w in words if w not in {"senior", "lead", "head", "manager",
                                          "director", "principal", "staff"}]
    if not core:
        core = words
    stem = r"\s+".join(re.escape(w) for w in core)
    return (rf"{stem}|"
            rf"(?:senior|head\s+of|lead|principal|staff|group)\s+.*{re.escape(core[0])}|"
            rf"{re.escape(core[0])}.*(?:manager|lead|head|director)")


GOVUK_API = ("https://www.gov.uk/api/content/government/publications/"
             "register-of-licensed-sponsors-workers")


def ensure_register():
    """Use a local register if present, else fetch today's from gov.uk."""
    if os.path.exists("data/register.csv"):
        return True

    print("No local register found - fetching the current one from gov.uk...",
          flush=True)
    ctx = ssl.create_default_context()
    hdr = {"User-Agent": "Mozilla/5.0 visa-sponsor-job-finder"}
    try:
        req = urllib.request.Request(GOVUK_API, headers=hdr)
        with urllib.request.urlopen(req, timeout=30, context=ctx) as r:
            meta = json.loads(r.read())
        atts = meta.get("details", {}).get("attachments", [])
        url = next((a["url"] for a in atts
                    if a.get("url", "").lower().endswith(".csv")), None)
        if not url and atts:
            url = atts[0].get("url")
        if not url:
            raise RuntimeError("no attachment listed on the gov.uk page")

        os.makedirs("data", exist_ok=True)
        req = urllib.request.Request(url, headers=hdr)
        with urllib.request.urlopen(req, timeout=180, context=ctx) as r:
            data = r.read()
        with open("data/register.csv", "wb") as fh:
            fh.write(data)
        print(f"Downloaded {len(data)/1e6:.1f} MB "
              f"({meta.get('public_updated_at','')[:10]})\n", flush=True)
        return True
    except Exception as e:
        print(f"\nCouldn't fetch it automatically: {e}\n")
        print("Download the 'Worker and Temporary Worker' CSV by hand from:")
        print(f"  {REGISTER_PAGE}")
        print("then save it as  data/register.csv  and run this again.")
        return False


def main():
    title = arg("--title")
    if not title:
        print(__doc__)
        sys.exit(1)
    sectors = arg("--sector")
    city = arg("--city")

    os.makedirs("data", exist_ok=True)
    if not ensure_register():
        sys.exit(1)

    fam, soc, rate, weight = classify_title(title)
    if BLOCKED_TITLE.search(title):
        print("!" * 70, flush=True)
        print(f'WARNING: "{title}" reads as an associate/executive-level title.', flush=True)
        print("Those map to SOC 3554 / 3552, which are medium-skilled and CANNOT", flush=True)
        print("be sponsored on the Skilled Worker route since 22 July 2025.", flush=True)
        print("Search the manager-level equivalent instead.", flush=True)
        print("!" * 70 + "\n", flush=True)

    targets = json.load(open(asset("targets.json")))
    if sectors:
        want = {s.strip() for s in sectors.split(",")}
        targets = {k: v for k, v in targets.items() if k in want}
        if not targets:
            sys.exit(f"no sectors matched {sectors}. available: "
                     f"{', '.join(json.load(open(asset('targets.json'))))}")

    base = json.load(open(asset("config.example.json")))
    cfg = {
        "register_csv": "data/register.csv",
        "register_columns": base["register_columns"],
        "sponsor_route_main": base["sponsor_route_main"],
        "sponsor_route_mobility_prefix": base["sponsor_route_mobility_prefix"],
        "role_families": {fam: {"weight": weight, "soc": soc,
                                "min_salary": rate,
                                "pattern": title_to_pattern(title)}},
        "exclude_titles": base["exclude_titles"],
        "location_pattern": rf"\b{re.escape(city.lower())}\b" if city else UK_CITIES,
        "sector_weights": base["sector_weights"],
        "targets": targets,
        "known_entities": base["known_entities"],
        "generic_brands": base["generic_brands"],
    }
    json.dump(cfg, open("config.json", "w"), indent=1)

    n = sum(len(v) for v in targets.values())
    print(f'Searching: "{title}"', flush=True)
    print(f"Occupation: {soc}", flush=True)
    print(f"Minimum salary for sponsorship: £{rate:,}", flush=True)
    print(f"Companies to check: {n}\n", flush=True)

    env = dict(os.environ, PYTHONPATH=HERE)
    for step, label in [("build_index.py", "Indexing the sponsor register"),
                        ("fetch_jobs.py", "Checking live job boards"),
                        ("match.py", "Resolving brand names to legal entities"),
                        ("rank.py", "Ranking")]:
        print(f"--- {label} ---", flush=True)
        r = subprocess.run([sys.executable, os.path.join(HERE, step),
                            "--config", "config.json"], env=env)
        if r.returncode != 0:
            sys.exit(f"failed at {step}")
        print()

    print("=" * 70)
    print("Shortlist:  out/SHORTLIST.md")
    print("Full data:  out/roles.csv   out/companies.csv")
    print()
    print("Before applying, read out/SHORTLIST.md - rows marked LIKELY or")
    print("PROBABLE are automated matches and have NOT been verified by hand.")
    print("Check a single company any time:  python3 scripts/lookup.py \"name\"")


if __name__ == "__main__":
    main()
