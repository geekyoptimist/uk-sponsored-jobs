#!/usr/bin/env python3
"""Probe 8 public ATS APIs for each target brand; keep in-country roles matching
the configured role families.

    python3 scripts/fetch_jobs.py --config config.json

Results cached to data/jobs_cache.json so re-runs are cheap.
"""
import json, os, re, ssl, sys, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from common import arg_config, all_targets, slug_variants

CTX = ssl.create_default_context()
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) job-search"}
CACHE = "data/jobs_cache.json"

# Large employers that use Workday exclusively. Extend for your market.
WORKDAY_TENANTS = {
    "Lloyds Banking Group": "lloydsbanking", "HSBC": "hsbc", "Barclays": "barclays",
    "NatWest": "natwest", "Santander UK": "santander", "Schroders": "schroders",
    "Legal and General": "legalandgeneral", "Aviva": "aviva", "Man Group": "mangroup",
    "LSEG": "lseg", "Refinitiv": "lseg", "Nasdaq": "nasdaq", "S&P Global": "spgi",
    "MSCI": "msci", "Mastercard": "mastercard", "Visa": "visa", "PayPal": "paypal",
    "ServiceNow": "servicenow", "Salesforce": "salesforce", "Workday": "workday",
    "Ocado": "ocado", "Sage": "sage", "eBay": "ebay", "Expedia": "expedia",
}
# Brands where a generic slug resolves to an unrelated company on a shared ATS.
FALSE_SLUGS = {"Amazon", "Uber", "Advanced", "Gnosis", "Omio", "Apple", "Meta"}


def get(url, timeout=18, data=None, headers=None):
    h = dict(UA)
    if headers:
        h.update(headers)
    try:
        req = urllib.request.Request(url, headers=h, data=data,
                                     method="POST" if data else "GET")
        with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
            return r.read() if r.status == 200 else None
    except Exception:
        return None


def jget(url, **kw):
    raw = get(url, **kw)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None


def _pack(ats, slug, jobs):
    return {"ats": ats, "slug": slug, "jobs": jobs} if jobs else None


def p_greenhouse(s):
    d = jget(f"https://boards-api.greenhouse.io/v1/boards/{s}/jobs")
    if not d or not d.get("jobs"):
        return None
    return _pack("greenhouse", s, [
        {"title": j.get("title", ""), "location": (j.get("location") or {}).get("name", ""),
         "url": j.get("absolute_url", ""), "updated": j.get("updated_at", "")}
        for j in d["jobs"]])


def p_lever(s):
    d = jget(f"https://api.lever.co/v0/postings/{s}?mode=json")
    if not isinstance(d, list) or not d:
        return None
    return _pack("lever", s, [
        {"title": j.get("text", ""), "location": (j.get("categories") or {}).get("location", ""),
         "url": j.get("hostedUrl", ""), "updated": str(j.get("createdAt", ""))}
        for j in d])


def p_ashby(s):
    d = jget(f"https://api.ashbyhq.com/posting-api/job-board/{s}")
    if not d or not d.get("jobs"):
        return None
    return _pack("ashby", s, [
        {"title": j.get("title", ""), "location": j.get("location", "") or "",
         "url": j.get("jobUrl", ""), "updated": j.get("publishedAt", "")}
        for j in d["jobs"]])


def p_smartrecruiters(s):
    d = jget(f"https://api.smartrecruiters.com/v1/companies/{s}/postings?limit=100")
    if not d or not d.get("content"):
        return None
    out = []
    for j in d["content"]:
        loc = j.get("location") or {}
        out.append({"title": j.get("name", ""),
                    "location": ", ".join(x for x in [loc.get("city"), loc.get("country")] if x),
                    "url": f"https://jobs.smartrecruiters.com/{s}/{j.get('id','')}",
                    "updated": j.get("releasedDate", "")})
    return _pack("smartrecruiters", s, out)


def p_workable(s):
    body = json.dumps({"query": "", "location": [], "department": [],
                       "worktype": [], "remote": []}).encode()
    d = jget(f"https://apply.workable.com/api/v3/accounts/{s}/jobs", data=body,
             headers={"Content-Type": "application/json"})
    if not d or not d.get("results"):
        return None
    out = []
    for j in d["results"]:
        loc = j.get("location") or {}
        out.append({"title": j.get("title", ""),
                    "location": ", ".join(x for x in [loc.get("city"), loc.get("country")] if x),
                    "url": f"https://apply.workable.com/{s}/j/{j.get('shortcode','')}",
                    "updated": j.get("published_on", "")})
    return _pack("workable", s, out)


def p_recruitee(s):
    d = jget(f"https://{s}.recruitee.com/api/offers/")
    if not d or not d.get("offers"):
        return None
    return _pack("recruitee", s, [
        {"title": j.get("title", ""),
         "location": ", ".join(x for x in [j.get("city"), j.get("country")] if x),
         "url": j.get("careers_url", ""), "updated": j.get("published_at", "")}
        for j in d["offers"]])


def p_personio(s):
    d = jget(f"https://{s}.jobs.personio.com/search.json")
    if not isinstance(d, list) or not d:
        return None
    return _pack("personio", s, [
        {"title": j.get("name", ""), "location": j.get("office", ""),
         "url": j.get("url", ""), "updated": j.get("createdAt", "")} for j in d])


def p_teamtailor(s):
    d = jget(f"https://{s}.teamtailor.com/jobs.json")
    jobs = d if isinstance(d, list) else (d or {}).get("jobs")
    if not jobs:
        return None
    return _pack("teamtailor", s, [
        {"title": j.get("title", ""), "location": str(j.get("location", "")),
         "url": j.get("url", ""), "updated": j.get("created-at", "")} for j in jobs])


WD_HOSTS = ["wd3", "wd1", "wd5", "wd2", "wd103"]
WD_BOARDS = ["External", "Careers", "External_Careers", "careers", "en-US/External"]


def p_workday(tenant):
    hdr = {"Content-Type": "application/json", "Accept": "application/json"}
    for host in WD_HOSTS:
        for board in WD_BOARDS:
            url = f"https://{tenant}.{host}.myworkdayjobs.com/wday/cxs/{tenant}/{board}/jobs"
            d = jget(url, data=json.dumps({"appliedFacets": {}, "limit": 20,
                                           "offset": 0, "searchText": ""}).encode(),
                     timeout=12, headers=hdr)
            if not d or not d.get("jobPostings"):
                continue
            posts = list(d["jobPostings"])
            for off in range(20, min(d.get("total", 0), 400), 20):
                d2 = jget(url, data=json.dumps({"appliedFacets": {}, "limit": 20,
                                                "offset": off, "searchText": ""}).encode(),
                          timeout=12, headers=hdr)
                if not d2 or not d2.get("jobPostings"):
                    break
                posts.extend(d2["jobPostings"])
            base = f"https://{tenant}.{host}.myworkdayjobs.com/en-US/{board.split('/')[-1]}"
            return _pack("workday", f"{tenant}/{host}/{board}", [
                {"title": j.get("title", ""), "location": j.get("locationsText", "") or "",
                 "url": base + (j.get("externalPath", "") or ""),
                 "updated": j.get("postedOn", "")} for j in posts])
    return None


PROVIDERS = [p_greenhouse, p_lever, p_ashby, p_smartrecruiters,
             p_workable, p_recruitee, p_personio, p_teamtailor]


def probe(t):
    brand = t["brand"]
    if brand not in FALSE_SLUGS:
        for slug in slug_variants(brand):
            for fn in PROVIDERS:
                r = fn(slug)
                if r:
                    return {**t, **r}
    tenant = WORKDAY_TENANTS.get(brand)
    if tenant:
        r = p_workday(tenant)
        if r:
            return {**t, **r}
    return {**t, "ats": None, "slug": None, "jobs": []}


def main():
    cfg = arg_config()
    os.makedirs("data", exist_ok=True)
    targets = all_targets(cfg)

    fams = {k: re.compile(v["pattern"], re.I | re.X)
            for k, v in cfg["role_families"].items()}
    excl = re.compile(cfg["exclude_titles"], re.I | re.X)
    loc_re = re.compile(cfg["location_pattern"], re.I | re.X)

    cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {}
    todo = [t for t in targets if t["brand"] not in cache]
    print(f"targets={len(targets)} cached={len(cache)} todo={len(todo)}", flush=True)

    done = 0
    with ThreadPoolExecutor(max_workers=14) as ex:
        futs = {ex.submit(probe, t): t for t in todo}
        for f in as_completed(futs):
            t = futs[f]
            try:
                cache[t["brand"]] = f.result()
            except Exception as e:
                cache[t["brand"]] = {**t, "ats": None, "slug": None,
                                     "jobs": [], "error": str(e)[:80]}
            done += 1
            if done % 25 == 0:
                print(f"  {done}/{len(todo)}", flush=True)
                json.dump(cache, open(CACHE, "w"))
    json.dump(cache, open(CACHE, "w"))

    hits, seen_url, seen_key = [], set(), set()
    for brand, rec in cache.items():
        if not rec.get("ats"):
            continue
        for j in rec["jobs"]:
            title = j.get("title", "")
            if excl.search(title):
                continue
            fam = next((k for k, rx in fams.items() if rx.search(title)), None)
            if not fam or not loc_re.search(j.get("location") or ""):
                continue
            key = (brand, title.strip().lower(), (j.get("location") or "").strip().lower())
            url = (j.get("url") or "").split("?")[0]
            if key in seen_key or (url and url in seen_url):
                continue
            seen_key.add(key)
            if url:
                seen_url.add(url)
            hits.append({"brand": brand, "sector": rec["sector"], "ats": rec["ats"],
                         "family": fam, "title": title, "location": j["location"],
                         "url": j["url"], "updated": j.get("updated", "")})

    json.dump(hits, open("data/jobs.json", "w"), indent=1)
    boards = sum(1 for r in cache.values() if r.get("ats"))
    print(f"\nboards found : {boards}/{len(cache)}  "
          f"({len(cache)-boards} unknown - NOT confirmed absent)")
    print(f"role hits    : {len(hits)}")
    from collections import Counter
    for k, v in Counter(h["family"] for h in hits).most_common():
        print(f"   {v:4d}  {k}")


if __name__ == "__main__":
    main()
