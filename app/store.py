"""SQLite store for photo paths + embeddings. Brute-force cosine search in numpy
(fast enough for tens of thousands of photos; swap for sqlite-vec later if needed)."""

import sqlite3
from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass
class Photo:
    id: int
    path: str
    score: float = 0.0


class VectorStore:
    def __init__(self, db_path: Path):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.execute(
            """CREATE TABLE IF NOT EXISTS photos (
                id INTEGER PRIMARY KEY,
                path TEXT UNIQUE NOT NULL,
                mtime REAL NOT NULL,
                embedding BLOB NOT NULL
            )"""
        )
        self._cache: tuple[np.ndarray, np.ndarray] | None = None

    def known_mtimes(self) -> dict[str, float]:
        return dict(self.conn.execute("SELECT path, mtime FROM photos"))

    def upsert(self, items: list[tuple[str, float, np.ndarray]]) -> None:
        self.conn.executemany(
            """INSERT INTO photos (path, mtime, embedding) VALUES (?, ?, ?)
               ON CONFLICT(path) DO UPDATE SET mtime=excluded.mtime, embedding=excluded.embedding""",
            [(p, m, e.astype(np.float32).tobytes()) for p, m, e in items],
        )
        self.conn.commit()
        self._cache = None

    def remove(self, paths: list[str]) -> None:
        self.conn.executemany("DELETE FROM photos WHERE path = ?", [(p,) for p in paths])
        self.conn.commit()
        self._cache = None

    def count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM photos").fetchone()[0]

    def get(self, photo_id: int) -> Photo | None:
        row = self.conn.execute("SELECT id, path FROM photos WHERE id = ?", (photo_id,)).fetchone()
        return Photo(*row) if row else None

    def sample(self, n: int) -> list[Photo]:
        rows = self.conn.execute("SELECT id, path FROM photos ORDER BY RANDOM() LIMIT ?", (n,))
        return [Photo(*row) for row in rows]

    def _matrix(self) -> tuple[np.ndarray, np.ndarray]:
        if self._cache is None:
            rows = self.conn.execute("SELECT id, embedding FROM photos").fetchall()
            ids = np.array([r[0] for r in rows], dtype=np.int64)
            vecs = (
                np.stack([np.frombuffer(r[1], dtype=np.float32) for r in rows])
                if rows
                else np.empty((0, 0), dtype=np.float32)
            )
            self._cache = (ids, vecs)
        return self._cache

    def search(self, query: np.ndarray, k: int) -> list[Photo]:
        ids, vecs = self._matrix()
        if len(ids) == 0:
            return []
        scores = vecs @ query  # vectors are L2-normalized → dot = cosine
        top = np.argsort(-scores)[:k]
        paths = dict(
            self.conn.execute(
                f"SELECT id, path FROM photos WHERE id IN ({','.join('?' * len(top))})",
                [int(ids[i]) for i in top],
            )
        )
        return [Photo(int(ids[i]), paths[int(ids[i])], float(scores[i])) for i in top]
