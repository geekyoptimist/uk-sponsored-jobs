# Public ATS job-board APIs

All public, no auth. Probe multiple slug variants per brand: `lowercase-nospace`, `lowercase-hyphen`, and the same with a trailing `.com/.io/.ai/.co` stripped.

Hit rate in practice: **~45% of target brands** yield a board across all eight. Report the miss count — the remainder are unknown, not confirmed absent.

## Greenhouse
```
GET https://boards-api.greenhouse.io/v1/boards/{slug}/jobs
```
`jobs[].title`, `.location.name`, `.absolute_url`, `.updated_at`

## Lever
```
GET https://api.lever.co/v0/postings/{slug}?mode=json
```
Returns a bare array. `[].text`, `.categories.location`, `.hostedUrl`

## Ashby
```
GET https://api.ashbyhq.com/posting-api/job-board/{slug}
```
`jobs[].title`, `.location`, `.jobUrl`, `.publishedAt`. Responses can exceed 400KB — don't cap the read buffer.

## SmartRecruiters
```
GET https://api.smartrecruiters.com/v1/companies/{slug}/postings?limit=100
```
`content[].name`, `.location.{city,country}`, id → `https://jobs.smartrecruiters.com/{slug}/{id}`

## Workable
```
POST https://apply.workable.com/api/v3/accounts/{slug}/jobs
Content-Type: application/json
{"query":"","location":[],"department":[],"worktype":[],"remote":[]}
```
`results[].title`, `.location.{city,country}`, `.shortcode`

## Recruitee
```
GET https://{slug}.recruitee.com/api/offers/
```
`offers[].title`, `.city`, `.country`, `.careers_url`

## Personio
```
GET https://{slug}.jobs.personio.com/search.json
```
Bare array. `[].name`, `.office`, `.url`

## Teamtailor
```
GET https://{slug}.teamtailor.com/jobs.json
```

## Workday

Hardest — needs tenant + host + board, none of which are guessable from the brand.

```
POST https://{tenant}.{host}.myworkdayjobs.com/wday/cxs/{tenant}/{board}/jobs
Content-Type: application/json
{"appliedFacets":{},"limit":20,"offset":0,"searchText":""}
```

- host: `wd1`, `wd2`, `wd3`, `wd5`, `wd103`
- board: `External`, `Careers`, `External_Careers`, `careers`, `en-US/External`
- Paginate on `offset`; `total` gives the count
- Job URL: `https://{tenant}.{host}.myworkdayjobs.com/en-US/{board}` + `jobPostings[].externalPath`

Maintain a hardcoded tenant map for large employers — banks, insurers, exchanges and legacy corporates use Workday almost exclusively, and these are exactly the reliable sponsors that startup-ATS probing misses. Example tenants: `lloydsbanking`, `hsbc`, `barclays`, `natwest`, `lseg`, `aviva`, `schroders`, `mastercard`.

## Guarding against false slug matches

A generic slug can resolve to an unrelated small company on a shared-domain ATS — probing `amazon` on Personio returns a real board that is not Amazon. Sanity-check any board whose job count or content is wildly inconsistent with the brand's size, and drop it.

## Not covered

LinkedIn-only posters, bespoke career sites, Taleo, SuccessFactors, iCIMS, Pinpoint, Eploy. This is a real coverage ceiling — state it rather than implying the result is the whole market.
