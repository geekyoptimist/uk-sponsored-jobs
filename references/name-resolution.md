# Brand name → legal entity name

Sponsor registers list the entity that holds the licence. That is frequently not the name on the website. Six layers, cheapest first.

## Layer 1 — Normalise

Strip corporate form and filler tokens, lowercase, drop punctuation, fold accents, expand `&` → `and`.

Strip: `limited|ltd|llp|llc|plc|inc|corp|company|holdings|group|international|global|uk|gb|services|solutions|systems|technologies|tech|labs|consulting|partners|associates|ventures|enterprises|operations|management|branch|establishment`

Keep both an aggressive form (brand core, for fuzzy matching) and a light form (punctuation only, for exact lookup). The aggressive form alone loses signal — `Wise Payments Limited` and `Wise Asset Management` both collapse to `wise`.

Catches: `Wise Payments Limited` → Wise. `Chainalysis UK Limited` → Chainalysis.

## Layer 2 — Trading-as

Registers carry `T/A`, `t/a` and `trading as` inline in the name field. In the UK register that is ~8,800 of 127k organisations — free, exact brand mappings.

Catches: `Roofoods Ltd t/a Deliveroo`. `New Wave Capital Ltd t/a Capital on Tap`. `Judilica UK Ltd t/a Legora`. `SCA Investments t/a Gousto`. `ZENLEADS INTERNATIONAL LIMITED (Trading as Apollo.io)`.

Parse the parenthetical form too.

## Layer 3 — Fuzzy token match

Token-set matching over the normalised forms. Require **all** brand tokens present in the legal name for high confidence; score down by the count of extra tokens.

Catches: ClearScore → `Clear Score Technology Limited` (word split). Legal & General → `Legal & General Resources Ltd` (ampersand).

**Guard against generic single-word brands.** Curve, Safe, Mode, Shares, Stake, Block, Square, Gemini, Ledger, Ripple, Kraken, Stripe and similar produce heavy false positives under fuzzy matching. Require an exact match for these, never fuzzy.

## Layer 4 — Companies House / national registry

Authoritative for official name, previous names and company number. UK public search needs no auth:

```
https://find-and-update.company-information.service.gov.uk/search/companies?q=<brand>
```

The API (free key) also returns `previous_company_names`, which catches rebrands directly.

## Layer 5 — Web lookup

The company's own **privacy policy or terms footer** almost always names the legal entity and company number. More reliable than the About page. Search `"<brand>" UK legal entity name` or fetch the policy page.

Catches: Checkout.com → `CHECKOUT LTD`. Zego → `EXTRACOVER LIMITED`.

## Layer 6 — Acquisition and rebrand history

Where the real value is. Zero string overlap, so no amount of fuzzy matching finds these — only knowing the corporate history does.

| Brand | Register entity | Why |
|---|---|---|
| Kraken | `Crypto Facilities Ltd` | acquired the UK entity in 2019 |
| Coinbase | `CB Payments Ltd` | holdco name |
| Refinitiv | `London Stock Exchange Group plc` | acquired 2021; Refinitiv absent from register |
| Dojo | `Paymentsense Limited` | rebranded |
| Abound | `Fintern Ltd` | rebranded |
| Airtable | `FORMAGRID UK LIMITED` | legal name always differed |
| Speechmatics | `CANTAB RESEARCH LIMITED` | original spinout name |
| HelloFresh | `Grocery Delivery E-services UK Ltd` | holdco |
| Block | `Squareup (UK) Ltd` | Square → Block rebrand |
| Elastic | `Elasticsearch Limited` | product name became company name |
| Zego | `EXTRACOVER LIMITED` | trades-as only |

Ask: did this company rebrand? get acquired? start under another name? spin out of a university?

## Verify before trusting

Real false positives from production runs:

| Brand | Wrongly matched | Actually |
|---|---|---|
| Stripe | `Stripe Partners` | a consultancy — correct is `Stripe Payments UK Ltd` |
| Notion | `Notion Capital Managers LLP` | a VC firm |
| Sardine | `The Sardine Factory Restaurant` | a restaurant |
| Ripple | `Ripple+ Limited` | correct is `Ripple Markets UK Ltd` |
| Elastic | `Elastic Path Software Inc.` | different company |
| Merkle Science | `Merkle UK Three Ltd` | dentsu's Merkle, unrelated |

**Same-name collisions are the worst failure mode** because they look right. Two unrelated companies named Kraken hold UK licences: `Crypto Facilities Ltd` (the exchange) and `Kraken Technologies Limited` (Octopus Energy's platform arm). A register search for "Kraken" returns the wrong one first.

Always emit alternates alongside the top match, and tier confidence explicitly.

## Absence is not proof

A brand missing from the register may mean no licence — or a legal name you haven't found. Run Layers 4–6 before telling someone a company cannot sponsor them.
