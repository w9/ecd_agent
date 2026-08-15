# Specs — Clinical Site Feasibility Agent

Behavior contract for the graded deliverables. Edit this file; implementation follows it.

**In scope:** answer free-text questions about (1) mock site enrollment data and (2) ingested public protocols, via one JSON API.

**Out of scope:** UI, cloud deploy, GxP, new protocol authoring, medical advice, real patient / PHI data.

---

## Routes

Every accepted query is classified as exactly one of:

| Route | When | Data used |
|-------|------|-----------|
| `site` | Quantitative site metric (rate, active trials, slots, capacity, ranking) | `sites` DB only |
| `protocol` | Eligibility / scientific / design question about a study | protocol chunks only |
| `hybrid` | Site recommendation that depends on protocol context | both |
| `reject` | Out of scope, unsafe, or too incomplete to act | none |

Lookalikes stay on the protocol side: “enrollment **criteria**” is eligibility, not a site rate.

---

## Query examples

`SITE-001` is known (rate 8.3, 2 active trials). `SITE-011` is zeros. `SITE-012` has null rate. `YYY` is unknown.

### In-scope

| Query | Route | Expected |
|-------|-------|----------|
| What is the enrollment rate for SITE-001? | `site` | “The monthly enrollment rate for SITE-001 is 8.3.” Cite `SITE-001`. Number comes from the DB, never the LLM. |
| How many active trials are at SITE-001? | `site` | “There are 2 active trials at SITE-001.” |
| How many remaining slots does SITE-001 have? | `site` | Answer with `24` from the DB. |
| Which oncology site has the highest enrollment rate? | `site` | Rank from the DB (e.g. SITE-007 at 9.1). No invented sites. |
| What is the minimum age for NCT04516746? | `protocol` | Answer only from retrieved chunks. Cite `nct_id` + section. |
| What are the inclusion criteria for this protocol? + `nct_id` | `protocol` | Grounded eligibility summary + citations. |
| Where should I run my next oncology trial given this protocol? + `nct_id` | `hybrid` | Recommend sites with reasons grounded in **both** protocol chunks and site rows. Cite both sources. |
| Enrollment criteria at SITE-001 | `protocol` | Treat as eligibility, not a site-rate lookup. Do not return 8.3 unless the protocol text says so. |

### Unknown / missing data (in-scope, but abstain)

| Query | Route | Expected |
|-------|-------|----------|
| What is the enrollment rate for site YYY? | `site` | “I don’t have any information on site YYY.” Do not invent a rate. |
| What is the enrollment rate for SITE-012? | `site` | Abstain on that metric (null in DB). Do not substitute another site’s rate. |
| What is the enrollment rate for SITE-011? | `site` | Report 0 **or** say there is no usable rate. Do not treat 0 as “unknown site.” |
| What is the dosing schedule for NCT00000001? (no matching chunks) | `protocol` | Abstain. Empty citations. `source: none`. |

### Incomplete / ambiguous

Well-formed JSON, but not enough to answer. HTTP 200, `route: reject`, ask for the missing piece. Do not guess a site or NCT.

| Query | Expected |
|-------|----------|
| What is the enrollment rate? | Ask which `site_id`. |
| What is the minimum age? (no `nct_id`, no NCT in text) | Ask for an NCT ID. |
| Tell me about the protocol. | Ask which study / NCT. |
| Tell me about SITE-001. | Optional: return the structured row (all known metrics). Otherwise ask which metric. **Default: return the row.** |

### Invalid / out of scope

| Query | Expected |
|-------|----------|
| Write me a new clinical protocol from scratch | `reject`. No site numbers, no fake protocol. |
| Should I enroll my patient in this trial? | `reject`. No medical advice. |
| Here is patient John Doe’s chart… | `reject`. No PHI. |
| *(empty / whitespace / >8000 chars / `nct_id` not `NCT`+8 digits)* | HTTP **422**. Not a routed answer. |

---

## API

`GET /health` → `{"status":"ok"}`

`POST /query`

```json
{"query": "What is the enrollment rate for SITE-001?", "nct_id": null}
```

```json
{
  "answer": "The monthly enrollment rate for SITE-001 is 8.3.",
  "route": "site",
  "source": "sites",
  "citations": [{"source": "sites", "site_id": "SITE-001"}]
}
```

Protocol / hybrid may pass `nct_id` (also accepted inside `query` text). “Attached protocol” in the brief = `nct_id` on the request. No file upload.

```json
{"query": "Where should I run my next oncology trial given this protocol?", "nct_id": "NCT04516746"}
```

```json
{
  "answer": "Based on the protocol, consider SITE-001 and SITE-007 because …",
  "route": "hybrid",
  "source": "hybrid",
  "citations": [
    {"source": "protocol", "nct_id": "NCT04516746", "section": "conditions"},
    {"source": "sites", "site_id": "SITE-001"}
  ]
}
```

| Field | Values |
|-------|--------|
| `route` | `site` \| `protocol` \| `hybrid` \| `reject` |
| `source` | `sites` \| `protocol` \| `hybrid` \| `none` |
| `citations[]` | site: `{source, site_id}`; protocol: `{source, nct_id, section}` |

| HTTP | When |
|------|------|
| 200 | Answer, abstain, or reject |
| 422 | Missing/empty `query`, oversized, malformed `nct_id` |
| 503 | LLM / upstream failure on a path that needs the model |

---

## Grounding

- Site numbers are copied from the tool/DB. If the model emits a different number, discard it.
- Protocol answers cite only retrieved chunks. Drop citations whose `nct_id`/section was not retrieved.
- No evidence (no row, null metric, empty retrieval) → abstain. `source: none` or a reject-style message. Never fill gaps from model memory.
- Hybrid answers must cite **both** sources when both were used.

---

## Failures

| Failure | Behavior |
|---------|----------|
| Bad request shape | 422 |
| Unknown site / null metric / empty retrieval | 200 + abstain, no invented facts |
| Malformed or missing tool result | Abstain; do not answer from free text |
| LLM down (protocol / hybrid) | 503 with an error body. Site-only queries still work. |
| Cached protocols / local DB unavailable | 200 + abstain (or 503 if the whole service cannot run) |
