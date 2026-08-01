#!/usr/bin/env python3
"""Check any company against the sponsor register.

    python3 scripts/lookup.py "kraken"
    python3 scripts/lookup.py "airtable" "some startup ltd"

Searches legal names, trading-as names and normalised brand forms, so it finds
entries whose legal name differs from the brand. Prints every plausible
candidate - same-name collisions are common, so read them all.
"""
import json, sys
from common import normalise, light_normalise, tokens

idx = json.load(open("data/index.json"))


def search(q):
    qn, ql = normalise(q), light_normalise(q)
    qt = tokens(qn)
    out = []
    for r in idx:
        s, why = 0, ""
        if qn and r["norm"] == qn:
            s, why = 100, "exact brand match"
        elif ql and r["light"] == ql:
            s, why = 95, "exact legal name"
        elif r["trading_as"] and qn and normalise(r["trading_as"]) == qn:
            s, why = 95, f"trading as '{r['trading_as']}'"
        elif ql and ql in r["light"]:
            s, why = 80, "substring of legal name"
        elif qt and qt <= set(r["tokens"]):
            s, why = 70, "all brand words present"
        elif qt and len(qt) > 1 and len(qt & set(r["tokens"])) >= len(qt) - 1:
            s, why = 50, "partial word overlap"
        if s:
            out.append((s, why, r))
    out.sort(key=lambda x: (-x[0], len(x[2]["legal_name"])))
    return out[:12]


def main(qs):
    for q in qs:
        print(f"\n=== {q} ===")
        res = search(q)
        if not res:
            print("  NOT FOUND under this name.")
            print("  -> Not proof they cannot sponsor. Run layers 4-6:")
            print("     Companies House / national registry (incl. previous names),")
            print("     the company's privacy policy footer (names the legal entity),")
            print("     and their acquisition + rebrand history.")
            continue
        for s, why, r in res:
            reloc = "  [holds mobility licence - moves staff internationally]" if r["gbm"] else ""
            print(f"  {s:3d}  {r['legal_name']}")
            print(f"       {r['city']} | {', '.join(r['routes'])}{reloc}")
            print(f"       via {why}")
        if len(res) > 1:
            print("  NOTE: multiple candidates. Unrelated companies share names -")
            print("        confirm which entity is actually your target.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    main(sys.argv[1:])
