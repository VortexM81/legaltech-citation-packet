import unittest

from src.citation_service import collect_research


class FakeClient:
    def __init__(self):
        self.upserts = 0

    def ensure_bucket(self, bucket):
        pass

    def search(self, query):
        return [{"url": "https://example.test/a"}, {"url": "https://example.test/a"}, {"url": "https://example.test/b"}]

    def rerank(self, query, candidates):
        return [{"document": url} for url in candidates]

    def scrape(self, url):
        return {"title": url.rsplit("/", 1)[-1], "content": "signed delivery deadline"}

    def embedding(self, text):
        return [1.0, 0.0]

    def query(self, collection, vector):
        return [] if self.upserts == 0 else [{"metadata": {"url": "duplicate"}}]

    def upsert(self, collection, vectors):
        self.upserts += 1

    def archive(self, bucket, key, document):
        self.archived = document


class CitationDecisionTest(unittest.TestCase):
    def test_repeated_source_is_kept_once_and_packet_is_ready(self):
        client = FakeClient()
        packet = collect_research("matter-1", "signed document delivery", client)
        self.assertEqual([item["url"] for item in packet["citations"]], ["https://example.test/a"])
        self.assertEqual(packet["status"], "ready_for_follow_up")
        self.assertEqual(client.archived["matter_id"], "matter-1")


if __name__ == "__main__":
    unittest.main()
