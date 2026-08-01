#!/usr/bin/env python3
"""Join live roles + register matches + eligibility -> ranked CSVs and shortlist.

    python3 scripts/rank.py --config config.json

Reads optional data/overrides.json for hand-verified results:
  {"verified": {"Brand": ["Legal Name On Register", "why"]},
   "not_sponsors": ["Brand", ...],
   "ambiguous": {"Brand": "why the automated match is untrustworthy"}}
"""
import csv, json, os, re
from common import arg_config


def seniority(title):
    t = title.lower()
    if re.search(r"\bintern\b|graduate|associate|assistant|executive\b|coordinator", t):
        return -1.5, "too junior - likely maps to a blocked occupation code"
    if re.search(r"\bvp\b|vice president|chief|\bcpo\b|\bcmo\b", t):
        return -0.8, "stretch seniority"
    if re.search(r"\bdirector\b", t):
        return -0.2, "stretch; director-level going rate applies"
    if re.search(r"\bhead of\b|\blead\b|\bprincipal\b|\bstaff\b", t):
        return 0.6, "good fit"
    if re.search(r"\bsenior\b|\bsnr\b", t):
        return 0.5, "good fit"
    if re.search(r"\bmanager\b", t):
        return 0.4, "good fit"
    return 0.0, ""


def main():
    cfg = arg_config()
    jobs = json.load(open("data/jobs.json"))
    matches = {m["brand"]: m for m in json.load(open("data/matches.json"))}
    idx = json.load(open("data/index.json"))
    by_legal = {}
    for r in idx:
        by_legal.setdefault(r["legal_name"].lower(), r)

    ov = json.load(open("data/overrides.json")) if os.path.exists("data/overrides.json") else {}
    verified = ov.get("verified", {})
    not_sponsors = set(ov.get("not_sponsors", []))
    ambiguous = ov.get("ambiguous", {})

    fams = cfg["role_families"]
    sw = cfg.get("sector_weights", {})
    rows = []

    for j in jobs:
        brand = j["brand"]
        if brand in not_sponsors:
            continue

        rec, conf, note = None, 0.0, ""
        if brand in verified:
            legal, note = verified[brand][0], verified[brand][1]
            rec, conf = by_legal.get(legal.lower()), 1.0
        elif brand in ambiguous:
            note, conf = ambiguous[brand], 0.4
            rec = by_legal.get((matches.get(brand, {}).get("legal_name") or "").lower())
        else:
            m = matches.get(brand, {})
            if m.get("matched"):
                rec = by_legal.get((m.get("legal_name") or "").lower())
                conf, note = m["confidence"], m["evidence"]
        if not rec:
            continue

        fam = fams.get(j["family"], {})
        sen, sen_note = seniority(j["title"])
        status, sp = (("VERIFIED" if brand in verified else "LIKELY"), 2.0) if conf >= 0.85 \
            else (("PROBABLE", 1.2) if conf >= 0.65 else ("NEEDS CHECK", 0.3))

        rows.append({
            "score": round(sw.get(j["sector"], 1.0) + fam.get("weight", 1.0)
                           + sp + (1.0 if rec["gbm"] else 0.0) + sen, 2),
            "brand": brand, "role": j["title"], "family": j["family"],
            "location": j["location"], "sector": j["sector"],
            "sponsor_status": status,
            "register_legal_name": rec["legal_name"], "register_city": rec["city"],
            "main_route": "Y" if rec["skilled_worker"] else "N",
            "reloc_signal": "Y" if rec["gbm"] else "N",
            "likely_soc": fam.get("soc", ""), "min_salary": fam.get("min_salary", ""),
            "seniority_note": sen_note, "name_resolution_note": note,
            "url": j["url"],
        })

    rows.sort(key=lambda r: (-r["score"], r["brand"]))
    os.makedirs("out", exist_ok=True)
    with open("out/roles.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    comp = {}
    for r in rows:
        c = comp.setdefault(r["brand"], {
            "brand": r["brand"], "sector": r["sector"],
            "register_legal_name": r["register_legal_name"],
            "register_city": r["register_city"], "sponsor_status": r["sponsor_status"],
            "reloc_signal": r["reloc_signal"],
            "name_resolution_note": r["name_resolution_note"],
            "open_roles": 0, "best_score": 0})
        c["open_roles"] += 1
        c["best_score"] = max(c["best_score"], r["score"])
    comps = sorted(comp.values(), key=lambda c: (-c["best_score"], -c["open_roles"]))
    with open("out/companies.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(comps[0].keys()))
        w.writeheader()
        w.writerows(comps)

    cache = json.load(open("data/jobs_cache.json"))
    boards = sum(1 for r in cache.values() if r.get("ats"))
    L = [f"# Sponsor-checked shortlist", "",
         f"**{len(rows)} live roles at {len(comps)} companies.**", "",
         "| Score | Company | Role | Sponsor | Reloc | Min salary |",
         "|---|---|---|---|---|---|"]
    for r in rows[:60]:
        L.append(f"| {r['score']} | [{r['brand']}]({r['url']}) | {r['role'][:54]} | "
                 f"{r['sponsor_status']} | {r['reloc_signal']} | {r['min_salary']} |")
    L += ["", "## Coverage and limits", "",
          f"- {boards} of {len(cache)} target companies had a reachable public job "
          f"board. The other {len(cache)-boards} are **unknown, not confirmed absent**.",
          "- A sponsor licence never guarantees sponsorship for a specific role.",
          "- Relocation signal is inferred from holding an intra-company transfer "
          "licence. It is not relocation data.",
          "- `VERIFIED` = manually confirmed. `LIKELY`/`PROBABLE` = automated match, "
          "unconfirmed. Check before investing in an application."]
    open("out/SHORTLIST.md", "w").write("\n".join(L))

    print(f"roles     : {len(rows)}  -> out/roles.csv")
    print(f"companies : {len(comps)} -> out/companies.csv")
    print(f"shortlist :          -> out/SHORTLIST.md")


if __name__ == "__main__":
    main()
