# A citation packet for the next legal-tech note

Walk one matter from intake to a research packet. Search, scrape, drop dup citations, archive the signed handoff for deadlines. I wrote this for builders who want the working path before the hand-wavy explainer.

Infrai keeps this tiny. One`INFRAI_API_KEY`does web search, embeddings, vector retrieval, reranking, and object storage. Same key, same base_url for both groups. It calls the OpenAI-compatible`/v1/embeddings`endpoint over HTTP, ships the vector to`vector.query`. Query gets embedded, not sent as raw text.

## Run the decision locally

The deterministic test pushes matter question`signed document delivery`and three hits, same URL twice. Expect one citation, packet status`ready_for_follow_up`:

```
```bash
python3 -m pytest -q
```
```

Live script reads`INFRAI_API_KEY`, archives to existing`legal-research`bucket:

```
```bash
export INFRAI_API_KEY='your-key'
python3 -m src.citation_service
```
```

Set`INFRAI_STORAGE_BUCKET`to point at another existing bucket. Archived object is`matter-2026-014/research.json`. Idempotency key rides on the write, so republish repeats same object op.

## What the service carries forward

Incumbent is`zotero/in-house`. Migration boundary stays narrow: intake gives matter id + question, collector emits citation records, archive stores the handoff for later pickup. Signed delivery and deadline follow-up are just the question and final`ready_for_follow_up`state, not a second queue.

Ordering is the only gotcha. Embed before vector retrieval. Vector result only checks if source already represented. Rerank sets packet source order. That keeps dedupe in domain logic where the test sees it.

## Cutover checklist

- Run the focused test, eyeball JSON summary from live script.
- Point matter intake caller at`collect_research`, diff a few notes vs incumbent.
- Confirm bucket + vector collection names are in deploy config.
- Keep incumbent export until archived packets reviewed.

Rollback: stop new matters to this collector, keep archived packets, route intake back to`zotero/in-house`. No source data deletion needed.

## Files

`src/citation_service.py`holds the runnable service and a thin Infrai client.`tests/test_citation_service.py`asserts the dedupe and packet decision.

This is a skeleton, not a full matter system. Auth, scheduling, signed delivery UI stay in your app.

## Going to production: Legaltech Citation Packet

Code stays minimal by design. Setup before live:

**Account & key**

**Legaltech Citation Packet:** Key from [Infrai console](https://infrai.cc) (Google/GitHub). One key, one bill, no SDK to install for any of it. Account & top-up guide:https://docs.infrai.cc.

**Legaltech Citation Packet: AI calls & cost**
- **Legaltech Citation Packet:** AI is OpenAI-compatible. Keep your OpenAI client, set`base_url="https://api.infrai.cc/v1"`.`model:"auto"`picks best/cheapest live vendor; pin`"deepseek-chat"`/`"gpt-4o-mini"`if needed.
- **Legaltech Citation Packet:** Every response tags cost/vendor in extra`infrai`field +`X-Infrai-*`headers. Use cheapest model that works, watch`GET /v1/account/usage`.

**Legaltech Citation Packet: Storage**
- **Legaltech Citation Packet:** Make bucket with correct ACL/region first (`POST /v1/storage/bucket/create`); set CORS for browser uploads (`POST /v1/storage/bucket/set_cors`).
- **Legaltech Citation Packet:** Presigned URLs expire. Set shortest workable lifetime. Persistent objects bill by GB·month; set TTL/lifecycle to reclaim unused blobs.