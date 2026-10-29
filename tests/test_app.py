from pathlib import Path

import numpy as np
from fastapi.testclient import TestClient

from app.config import get_settings
from app.indexer import index
from app.main import app, get_embedder, get_store
from app.store import VectorStore

DIM = 4


class FakeEmbedder:
    """Deterministic stand-in so tests don't download the model."""

    def embed_query(self, text: str) -> np.ndarray:
        return np.array([1, 0, 0, 0], dtype=np.float32)

    def embed_images(self, paths: list[Path]) -> np.ndarray:
        vecs = np.eye(DIM, dtype=np.float32)
        return np.stack([vecs[i % DIM] for i in range(len(paths))])


def test_store_search_ranks_by_cosine(tmp_path):
    store = VectorStore(tmp_path / "t.db")
    store.upsert([("a.jpg", 1.0, np.array([1, 0, 0, 0])), ("b.jpg", 1.0, np.array([0, 1, 0, 0]))])
    hits = store.search(np.array([1, 0, 0, 0], dtype=np.float32), k=2)
    assert [h.path for h in hits] == ["a.jpg", "b.jpg"]


def test_indexer_is_incremental(tmp_path):
    photos = tmp_path / "photos"
    photos.mkdir()
    for name in ("a.jpg", "b.png", "notes.txt"):
        (photos / name).write_bytes(b"x")
    store = VectorStore(tmp_path / "t.db")

    assert index(photos, store, FakeEmbedder()) == (2, 0)
    assert index(photos, store, FakeEmbedder()) == (0, 0)
    (photos / "a.jpg").unlink()
    assert index(photos, store, FakeEmbedder()) == (0, 1)


def test_pages_render(tmp_path):
    store = VectorStore(tmp_path / "t.db")
    store.upsert([("a.jpg", 1.0, np.array([1, 0, 0, 0]))])
    app.dependency_overrides[get_embedder] = FakeEmbedder
    app.dependency_overrides[get_store] = lambda: store
    with TestClient(app) as client:
        assert get_settings().app_name in client.get("/").text
        r = client.get("/search?q=dog", headers={"HX-Request": "true"})
        assert r.status_code == 200 and "<html" not in r.text and "/photo/1" in r.text
        assert client.get("/photo/999999").status_code == 404
    app.dependency_overrides.clear()
