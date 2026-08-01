#!/usr/bin/env python3
"""Match target brands -> sponsor register entries.

    python3 scripts/match.py --config config.json

Confidence tiers:
  1.00 known_entity  - config-supplied verified bridge (layer 4-6)
  0.95 exact_norm    - normalised brand == normalised legal name
  0.92 trading_as    - matched a "t/a <brand>" field
  0.88 exact_light   - punctuation-only normalisation matches
  0.72-0.85 subset   - all brand tokens present in legal name
  0.50-0.65 partial  - some overlap; needs human review

Nothing below 0.85 should be presented as fact.
"""
import json
from collections import defaultdict
from common import arg_config, all_targets, normalise, light_normalise, tokens


def score(rec, brand, bn, bt, bl, known, generic):
    ke = known.get(brand.lower())
    if ke:
        kel = light_normalise(ke)
        if rec["light"] == kel or kel in rec["light"] or rec["light"] in kel:
            return 1.00, f"known_entity:{ke}"

    if bn and rec["norm"] == bn:
        return 0.95, "exact_norm"

    if rec["trading_as"] and bn and normalise(rec["trading_as"]) == bn:
        return 0.92, f"trading_as:{rec['trading_as']}"

    if bl and rec["light"] == bl:
        return 0.88, "exact_light"

    # generic single-word brands: exact only, fuzzy produces garbage
    if bn in generic or not bt:
        return None

    rt = set(rec["tokens"])
    inter = bt & rt
    if not rt or not inter:
        return None

    if bt <= rt:
        extra = len(rt - bt)
        return (0.85 if extra == 0 else 0.80 if extra == 1 else 0.72), \
               f"subset(+{extra} extra)"

    if len(bt) >= 2 and len(inter) >= 2:
        jac = len(inter) / len(bt | rt)
        if jac >= 0.5:
            return 0.65, f"partial(jaccard={jac:.2f})"
        if jac >= 0.34:
            return 0.50, f"partial(jaccard={jac:.2f})"
    return None


def main():
    cfg = arg_config()
    idx = json.load(open("data/index.json"))
    by_alias = json.load(open("data/by_alias.json"))
    by_token = json.load(open("data/by_token.json"))
    known = {k.lower(): v for k, v in cfg.get("known_entities", {}).items()}
    generic = set(cfg.get("generic_brands", []))

    results = []
    for t in all_targets(cfg):
        brand = t["brand"]
        bn, bl = normalise(brand), light_normalise(brand)
        bt = tokens(bn)

        cand = set()
        for key in {bn, bl}:
            cand.update(by_alias.get(key, []))
        for tok in bt:
            cand.update(by_token.get(tok, []))
        ke = known.get(brand.lower())
        if ke:
            cand.update(by_alias.get(light_normalise(ke), []))
            for tok in tokens(normalise(ke)):
                cand.update(by_token.get(tok, []))

        scored = []
        for i in cand:
            rec = idx[i]
            s = score(rec, brand, bn, bt, bl, known, generic)
            if not s:
                continue
            conf, ev = s
            bonus = (0.02 if rec["skilled_worker"] else 0) + (0.01 if rec["gbm"] else 0)
            scored.append((conf + bonus, conf, ev, rec))
        scored.sort(key=lambda x: -x[0])

        if not scored:
            results.append({**t, "matched": False, "confidence": 0.0,
                            "legal_name": None, "evidence": "no_match",
                            "alternates": []})
            continue
        top = scored[0]
        results.append({
            **t, "matched": True, "confidence": round(top[1], 2),
            "legal_name": top[3]["legal_name"], "trading_as": top[3]["trading_as"],
            "city": top[3]["city"], "routes": top[3]["routes"],
            "skilled_worker": top[3]["skilled_worker"], "gbm": top[3]["gbm"],
            "evidence": top[2],
            "alternates": [{"legal_name": b[3]["legal_name"], "city": b[3]["city"],
                            "confidence": round(b[1], 2), "evidence": b[2]}
                           for b in scored[1:4]],
        })

    json.dump(results, open("data/matches.json", "w"), indent=1)
    hi = [r for r in results if r["matched"] and r["confidence"] >= 0.85]
    mid = [r for r in results if r["matched"] and 0.65 <= r["confidence"] < 0.85]
    lo = [r for r in results if r["matched"] and r["confidence"] < 0.65]
    no = [r for r in results if not r["matched"]]
    print(f"targets={len(results)}  high={len(hi)}  mid={len(mid)}  "
          f"low={len(lo)}  none={len(no)}")
    print("\nNO MATCH - run lookup.py and layers 4-6 before concluding "
          "these cannot sponsor:")
    for r in no:
        print(f"  [{r['sector']:>12}] {r['brand']}")
    if lo:
        print("\nLOW CONFIDENCE - verify by hand:")
        for r in lo:
            print(f"  {r['brand']:24s} -> {r['legal_name']}  ({r['evidence']})")


if __name__ == "__main__":
    main()
