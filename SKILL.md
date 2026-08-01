---
name: visa-sponsor-job-finder
description: Find real, currently-open jobs at companies licensed to sponsor work visas, matched to a CV. Use when someone wants visa-sponsored jobs, relocation roles, or asks "which companies can sponsor me" — for the UK Home Office sponsor register (also adaptable to other countries' sponsor lists). Handles the hard part: government registers list LEGAL entity names, not brand names, so Kraken appears as "Crypto Facilities Ltd" and Airtable as "Formagrid UK Limited".
---

# Visa-Sponsored Job Finder

Turn a government sponsor register (a list of ~130k legal entity names and nothing else) plus a CV into a ranked list of **live job postings you can actually apply to**.

## The problem this solves

Sponsor registers are near-useless raw. Three reasons:

1. **They list legal entities, not brands.** Searching "Kraken" misses it — the crypto exchange sponsors under `Crypto Facilities Ltd` (a 2019 acquisition). Coinbase is `CB Payments Ltd`. Airtable is `FORMAGRID UK LIMITED`. Dojo is `Paymentsense Limited`.
2. **They contain no jobs.** A licence means a company *can* sponsor, not that it's hiring.
3. **Holding a licence doesn't make a role eligible.** Most countries gate on occupation classification and salary. Applying to an ineligible role wastes weeks.

## Quick path — use this unless they asked for something custom

Most people asking will not be technical. Do not hand them commands to run. Ask for a job title if they haven't given one, then run this yourself in a working directory:

```bash
python3 scripts/run.py --title "product marketing manager"
```

It needs nothing set up. It downloads the current register from gov.uk itself, ships with a 561-company target list, derives the occupation code and salary floor from the title, and writes `out/SHORTLIST.md`. Takes a few minutes, mostly waiting on job boards.

Narrow it with `--sector crypto,fintech` (crypto, fintech, b2b_saas, ai, consumer, health_prop_climate) or `--city london`.

Then **report the results in the conversation** — top roles with company, title, salary floor and link. Don't just point at the file.

Two things to always say back:
- If their title triggered the blocked-occupation warning, lead with that. It's the difference between a viable search and a wasted month.
- Which rows are `VERIFIED` vs `LIKELY`. Never present an unverified match as fact.

Use the staged path below only when they want a custom company list, different scoring, or another country's register.

## Do these in order

### Step 0 — Eligibility first, always

**Never skip this.** Establish which occupation codes the person's target titles map to, and each code's salary floor. A whole shortlist is worthless if the roles can't be sponsored.

For the UK, see `references/soc-eligibility.md`. The trap: since 22 July 2025 the Skilled Worker route requires RQF Level 6+, which **blocks SOC 3554 (marketing associate professionals) and 3552 (business sales executives)** — where most mid-level marketing and sales roles get coded. The same work at manager title codes to 2432 and is eligible.

Always re-verify against the official source; thresholds change at least annually.

### Step 1 — Parse the CV

Extract: years of experience, seniority, function, domain/sector, location history. Derive the target role titles and the sector weighting used for ranking later.

### Step 2 — Build the register index

```bash
python3 scripts/build_index.py --register data/register.csv
```

Normalises names, extracts `t/a` (trading-as) brands, builds inverted indexes on aliases and tokens. Outputs `data/index.json`.

### Step 3 — Build a target company list

Curate brands the person would plausibly work for, grouped by sector. **Do not try to resolve all 130k register names to brands** — that is the wrong direction and produces garbage. Invert the problem: start from a few hundred target brands and look each one up.

Edit `config.json` (see `config.example.json`).

### Step 4 — Find live jobs

```bash
python3 scripts/fetch_jobs.py --config config.json
```

Probes 8 public ATS APIs (Greenhouse, Lever, Ashby, SmartRecruiters, Workable, Recruitee, Personio, Workday) with multiple slug variants per brand. See `references/ats-providers.md` for endpoints.

Expect **~45% of brands to yield a board**. Report that number — silent partial coverage reads as completeness.

### Step 5 — Resolve brand → legal name

```bash
python3 scripts/match.py --config config.json
```

Six layers, cheapest first. Full playbook in `references/name-resolution.md`.

**Automated matching alone is not safe.** Real false positives from production runs: Stripe → *Stripe Partners* (a consultancy), Notion → *Notion Capital Managers LLP* (a VC), Sardine → *The Sardine Factory Restaurant*. Anything a person will act on must be eyeballed. Mark every row `VERIFIED` / `LIKELY` / `NEEDS CHECK` and never blur that line.

Run the deep search on unmatched and suspicious brands before concluding a company can't sponsor:

```bash
python3 scripts/lookup.py "company name"
```

### Step 6 — Rank and ship

```bash
python3 scripts/rank.py --config config.json
```

Scores each role on sector fit + role-family fit + sponsorship confidence + relocation signal + seniority fit. Emits a roles CSV, a companies CSV, and a markdown shortlist.

## Relocation packages

Registers don't contain them. The usable proxy: a company holding **both** a standard work visa licence **and** an intra-company transfer licence already moves staff across borders. Label this as inference, never as fact.

## Reporting rules

State plainly:
- How many target brands had a reachable job board, and that the rest are unknown, not absent
- That a licence never guarantees sponsorship for a specific role
- Which matches are verified vs automated
- That relocation signal is inferred

A shortlist that overstates its own confidence costs someone weeks of applications.

## Also check the no-sponsor routes

Many countries have talent/skilled-independent visas needing no employer at all — UK Global Talent, and equivalents elsewhere. For founders, senior operators, or anyone with public achievements, this is often the stronger route: no salary floor, no employer lock-in, and it unlocks every company that *doesn't* hold a licence. Assess it in parallel rather than instead.

## Getting the register

UK: Home Office "Register of licensed sponsors: workers", published as CSV, updated daily —
<https://www.gov.uk/government/publications/register-of-licensed-sponsors-workers>

Other countries publish equivalents. The method transfers; only Step 0 and the register schema change.
