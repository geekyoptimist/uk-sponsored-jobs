# visa-sponsor-job-finder

A Claude Code skill that turns a government visa-sponsor register into a ranked list of **live jobs you can actually apply to**.

Built for the UK Home Office sponsor register. The method transfers to any country that publishes one.

## The problem

The UK publishes every company licensed to sponsor a work visa. It's ~127,000 organisations. It is also close to useless as-is:

1. **It lists legal entities, not brands.** Search "Kraken" and you'll miss it — the crypto exchange sponsors under `Crypto Facilities Ltd`, a company it acquired in 2019. Coinbase is `CB Payments Ltd`. Airtable is `FORMAGRID UK LIMITED`. Dojo is `Paymentsense Limited`. Refinitiv isn't on the register at all — LSEG bought it.
2. **It contains no jobs.** A licence means a company *can* sponsor. Not that it's hiring.
3. **A licence doesn't make a role eligible.** Since July 2025 the UK requires RQF Level 6+, which blocks the occupation codes most mid-level marketing and sales roles get assigned. You can apply to a sponsor's open role and still be unsponsorable.

## What it does

```
register CSV ──▶ index + trading-as extraction
                          │
CV ──▶ target brands ──▶ 8 ATS APIs ──▶ live roles
                          │
                 6-layer name resolution
                          │
              eligibility filter + ranking
                          │
                 roles.csv · companies.csv · SHORTLIST.md
```

## Install

```bash
git clone <this repo> ~/.claude/skills/visa-sponsor-job-finder
```

Claude Code picks it up automatically. Or just read `SKILL.md` and run the scripts yourself.

## Use

Put the folder in `~/.claude/skills/`, then just ask:

> "Find me product marketing manager jobs in the UK that sponsor visas"

No setup, no API keys, no manual downloads. It fetches today's register from gov.uk itself.

Follow-ups work the way you'd expect — *"only crypto and fintech"*, *"London only"*, *"what about product manager roles?"*

### Or run it yourself

```bash
mkdir my-search && cd my-search
cp -r ~/.claude/skills/visa-sponsor-job-finder/scripts .
python3 scripts/run.py --title "product marketing manager"
```

Ships with a 561-company target list, works out the occupation code and salary floor from your title, checks every company's live job board, resolves brand names to legal entities, writes `out/SHORTLIST.md`. Add `--sector crypto,fintech` or `--city london`.

Give it a title that can't be sponsored and it stops you before doing any work:

```
WARNING: "marketing executive" reads as an associate/executive-level title.
Those map to SOC 3554 / 3552, which are medium-skilled and CANNOT
be sponsored on the Skilled Worker route since 22 July 2025.
```

### Custom company list or scoring

```bash
cp ~/.claude/skills/visa-sponsor-job-finder/config.example.json config.json
# edit config.json
python3 scripts/build_index.py --config config.json
python3 scripts/fetch_jobs.py  --config config.json
python3 scripts/match.py       --config config.json
python3 scripts/rank.py        --config config.json
```

Check any single company:

```bash
python3 scripts/lookup.py "kraken"
```

## The six layers of name resolution

| # | Layer | Catches |
|---|---|---|
| 1 | Normalise suffixes | `Wise Payments Limited` → Wise |
| 2 | Trading-as field | `Roofoods Ltd t/a Deliveroo` |
| 3 | Fuzzy token match | ClearScore → `Clear Score Technology Limited` |
| 4 | Companies House | official + previous names |
| 5 | Privacy-policy footer | Checkout.com → `CHECKOUT LTD` |
| 6 | Acquisition history | Kraken → `Crypto Facilities Ltd` |

Layer 6 is where the value is, and no amount of string matching gets you there.

Full playbook: `references/name-resolution.md`.

## Automated matching is not enough

Real false positives from a production run:

- Stripe → `Stripe Partners` (a consultancy)
- Notion → `Notion Capital Managers LLP` (a VC firm)
- Sardine → `The Sardine Factory Restaurant`
- Elastic → `Elastic Path Software` (different company)

And the worst failure mode — **two unrelated companies named Kraken hold UK licences.** `Crypto Facilities Ltd` is the exchange. `Kraken Technologies Limited` is Octopus Energy's platform arm. A register search returns the wrong one first.

Every row is tiered `VERIFIED` / `LIKELY` / `PROBABLE` / `NEEDS CHECK`. Nothing below VERIFIED should be treated as fact.

## Honest limits

- ~45% of target brands yield a public job board. The rest are **unknown, not confirmed absent**. The tool reports this number rather than hiding it.
- A licence never guarantees sponsorship for a specific role — that's a per-hire decision.
- Relocation packages appear nowhere in the register. The `reloc_signal` column infers from a company holding an intra-company transfer licence, which means it already moves staff across borders. Inference, not data.
- Not immigration advice. Verify eligibility rules against official sources — they change at least annually.

## Also check the no-sponsor routes

Most countries have a talent visa needing no employer. The UK's Global Talent has no salary floor, no employer lock-in, and unlocks every company *without* a licence. For founders and senior operators it's often the better route. Assess it in parallel.

## Licence

MIT. No warranty. Immigration decisions are yours.
