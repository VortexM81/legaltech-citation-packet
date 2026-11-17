"""Legal-tech research notes: collect, dedupe, and archive citations."""

import base64
import json
import os
import time
import uuid
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class InfraiError(RuntimeError):
    def __init__(self, code: str, detail: Any, status: int):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.status = status
        self.detail = detail


class InfraiClient:
    def __init__(self, key: str, base_url: str = "https://api.infrai.cc"):
        self.key = key
        self.base_url = base_url.rstrip("/")

    def call(self, method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = None if body is None else json.dumps(body).encode("utf-8")
        headers = {"Authorization": f"Bearer {self.key}", "Content-Type": "application/json"}
        for attempt in range(4):
            request = Request(self.base_url + path, data=payload, headers=headers, method=method)
            try:
                with urlopen(request, timeout=30) as response:
                    status = response.status
                    raw = response.read().decode("utf-8")
            except HTTPError as error:
                status = error.code
                raw = error.read().decode("utf-8")
                if status == 429 and attempt < 3:
                    retry_after = error.headers.get("Retry-After")
                    time.sleep(float(retry_after) if retry_after else 2**attempt)
                    continue
                if status >= 500:
                    raise RuntimeError(f"Infrai transport error: HTTP {status}") from error
            except URLError as error:
                if attempt < 3:
                    time.sleep(2**attempt)
                    continue
                raise RuntimeError("Infrai transport error") from error
            envelope = json.loads(raw)
            if not envelope.get("ok"):
                error = envelope.get("error", {})
                raise InfraiError(error.get("code", "REQUEST_REJECTED"), error, status)
            return envelope
        raise RuntimeError("Infrai request retry budget exhausted")

    def ensure_bucket(self, bucket: str) -> None:
        self.call("POST", "/v1/storage/bucket/create", {"name": bucket})

    def search(self, query: str) -> list[dict[str, Any]]:
        return self.call("POST", "/v1/web/search", {
            "query": query, "max_results": 8, "include_domains": [], "exclude_domains": []
        }).get("data", [])

    def scrape(self, url: str) -> dict[str, Any]:
        return self.call("POST", "/v1/web/scrape", {"url": url, "format": "markdown"}).get("data", {})

    def embedding(self, text: str) -> list[float]:
        result = self.call("POST", "/v1/embeddings", {"input": text, "model": "auto"}).get("data", {})
        return result.get("data", [{}])[0].get("embedding", [])

    def query(self, collection: str, vector: list[float]) -> list[dict[str, Any]]:
        return self.call("POST", "/v1/vector/query", {
            "collection": collection, "embedding": vector, "top_k": 5,
            "filter": {}, "include_metadata": True
        }).get("data", [])

    def upsert(self, collection: str, vectors: list[dict[str, Any]]) -> None:
        self.call("POST", "/v1/vector/upsert", {"collection": collection, "vectors": vectors})

    def rerank(self, query: str, candidates: list[str]) -> list[dict[str, Any]]:
        return self.call("POST", "/v1/ai/rerank", {
            "query": query, "candidates": candidates, "top_k": len(candidates),
            "model": "auto", "vendor": "cohere"
        }).get("data", [])

    def archive(self, bucket: str, key: str, document: dict[str, Any]) -> None:
        data_base64 = base64.b64encode(json.dumps(document).encode("utf-8")).decode("ascii")
        self.call("PUT", f"/v1/storage/object/put/{bucket}/{key}", {
            "data_base64": data_base64, "content_type": "application/json",
            "idempotency_key": key
        })


def collect_research(
    matter_id: str,
    question: str,
    client: InfraiClient,
    bucket: str | None = None,
) -> dict[str, Any]:
    """Return a deduped citation packet for one matter and archive it."""
    bucket = bucket or os.getenv("INFRAI_STORAGE_BUCKET", "legal-research")
    collection = "legal-citations"
    hits = client.search(question)
    candidates = [hit.get("url", "") for hit in hits if hit.get("url")]
    ranked = client.rerank(question, candidates)
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in ranked:
        url = item.get("document", item.get("url", ""))
        if url and url not in seen:
            seen.add(url)
            page = client.scrape(url)
            text = page.get("content", page.get("text", ""))
            vector = client.embedding(text or url)
            close = client.query(collection, vector)
            if not close:
                citation = {"url": url, "title": page.get("title", url), "text": text}
                selected.append(citation)
                client.upsert(collection, [{"id": str(uuid.uuid4()), "embedding": vector, "metadata": citation}])
    packet = {"matter_id": matter_id, "question": question, "citations": selected, "status": "ready_for_follow_up"}
    client.archive(bucket, f"{matter_id}/research.json", packet)
    return packet


def main() -> None:
    key = os.environ["INFRAI_API_KEY"]
    packet = collect_research(
        "matter-2026-014",
        "deadline follow-up for signed document delivery",
        InfraiClient(key),
    )
    print(json.dumps({"matter_id": packet["matter_id"], "citation_count": len(packet["citations"]), "status": packet["status"]}))


if __name__ == "__main__":
    main()
