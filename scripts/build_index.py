#!/usr/bin/env python3
"""Build a searchable index over a sponsor register CSV.

    python3 scripts/build_index.py --config config.json

Applies layers 1-2 of name resolution (normalise, trading-as) and writes
inverted indexes for fast candidate generation in match.py.
"""
import csv, json, os
from collections import defaultdict
from common import (arg_config, normalise, light_normalise, tokens,
                    extract_trading_as)


def main():
    cfg = arg_config()
    path = cfg["register_csv"]
    col = cfg["register_columns"]
    main_route = cfg["sponsor_route_main"]
    mob_prefix = cfg["sponsor_route_mobility_prefix"]
    os.makedirs("data", exist_ok=True)

    rows = 0
    orgs = {}
    with open(path, newline="", encoding="utf-8-sig") as fh:
        for r in csv.DictReader(fh):
            name = (r.get(col["name"]) or "").strip()
            if not name:
                continue
            rows += 1
            city = (r.get(col["city"]) or "").strip()
            key = (light_normalise(name), city.lower())
            o = orgs.setdefault(key, {"name": name, "city": city,
                                      "county": (r.get(col.get("county", "")) or "").strip(),
                                      "routes": set(), "ratings": set()})
            o["routes"].add((r.get(col["route"]) or "").strip())
            o["ratings"].add((r.get(col.get("rating", "")) or "").strip())

    index = []
    for (lkey, _), o in orgs.items():
        raw = o["name"]
        ta, legal_part = extract_trading_as(raw)
        norm = normalise(legal_part) or normalise(raw)

        aliases = {norm, lkey}
        if ta:
            aliases.add(normalise(ta))
            aliases.add(light_normalise(ta))
        aliases = {a for a in aliases if a}

        routes = sorted(o["routes"])
        index.append({
            "legal_name": raw, "trading_as": ta, "city": o["city"],
            "county": o["county"], "norm": norm, "light": lkey,
            "aliases": sorted(aliases), "tokens": sorted(tokens(norm)),
            "routes": routes, "ratings": sorted(o["ratings"]),
            "skilled_worker": any(r == main_route for r in routes),
            "gbm": any(r.startswith(mob_prefix) for r in routes),
        })

    by_alias, by_token = defaultdict(list), defaultdict(list)
    for i, rec in enumerate(index):
        for a in rec["aliases"]:
            by_alias[a].append(i)
        for t in rec["tokens"]:
            by_token[t].append(i)

    json.dump(index, open("data/index.json", "w"))
    json.dump(by_alias, open("data/by_alias.json", "w"))
    json.dump({k: v for k, v in by_token.items() if len(v) <= 4000},
              open("data/by_token.json", "w"))

    print(f"register rows   : {rows}")
    print(f"deduped orgs    : {len(index)}")
    print(f"with trading-as : {sum(1 for r in index if r['trading_as'])}")
    print(f"main route      : {sum(1 for r in index if r['skilled_worker'])}")
    print(f"+ mobility      : {sum(1 for r in index if r['skilled_worker'] and r['gbm'])}"
          f"   <- best relocation proxy")


if __name__ == "__main__":
    main()
