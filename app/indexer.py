"""Incremental indexer: embeds new/changed photos, drops deleted ones.

Run: uv run python -m app.indexer
"""

from pathlib import Path

from app.config import get_settings
from app.embedder import Embedder, GemmaEmbedder
from app.store import VectorStore

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}
BATCH = 32


def scan(root: Path) -> dict[str, float]:
    return {
        str(p): p.stat().st_mtime
        for p in root.rglob("*")
        if p.is_file() and p.suffix.lower() in IMAGE_EXTS and not p.name.startswith(".")
    }


def index(root: Path, store: VectorStore, embedder: Embedder) -> tuple[int, int]:
    on_disk = scan(root)
    known = store.known_mtimes()

    stale = [p for p in known if p not in on_disk]
    store.remove(stale)

    todo = [p for p, m in on_disk.items() if known.get(p) != m]
    for i in range(0, len(todo), BATCH):
        batch = todo[i : i + BATCH]
        vecs = embedder.embed_images([Path(p) for p in batch])
        store.upsert([(p, on_disk[p], v) for p, v in zip(batch, vecs)])
        print(f"indexed {min(i + BATCH, len(todo))}/{len(todo)}")
    return len(todo), len(stale)


def main() -> None:
    s = get_settings()
    store = VectorStore(s.db_path)
    added, removed = index(s.photos_root, store, GemmaEmbedder(s.model_id, s.embed_dim))
    print(f"done: {added} embedded, {removed} removed, {store.count()} total")


if __name__ == "__main__":
    main()
