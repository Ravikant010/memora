"""Build a static, backend-free prototype of the app for a portfolio site.

Renders the real Jinja templates, precomputes results for a set of example queries with
the real model, and copies resized photos. Free-text queries are matched to the closest
preset by word overlap (the prototype can't run the model in the browser).

Run from the project root:  uv run python -m portfolio.build_prototype
"""

import json
import re
import shutil
from pathlib import Path

from PIL import Image

from app.config import get_settings
from app.embedder import GemmaEmbedder
from app.main import templates
from app.store import VectorStore

OUT = Path(__file__).parent / "prototype"
STATIC = Path(__file__).resolve().parent.parent / "app" / "static"
TOP_K = 12
QUERIES = [
    "dog playing frisbee",
    "pizza on a table",
    "people skiing",
    "red bus",
    "cat on a laptop",
    "बच्चे फुटबॉल खेल रहे हैं",
    "giraffe",
    "surfer riding a wave",
    "birthday cake with candles",
    "train at a station",
    "plage au coucher du soleil",
    "teddy bear",
]


def render(name: str, **ctx) -> str:
    return templates.env.get_template(name).render(**ctx)


def save_image(store: VectorStore, photo_id: int, used: set[int]) -> None:
    if photo_id in used:
        return
    used.add(photo_id)
    p = store.get(photo_id)
    with Image.open(p.path) as im:
        im = im.convert("RGB")
        im.thumbnail((900, 900))
        im.save(OUT / "img" / f"{photo_id}.jpg", quality=82, optimize=True)


def staticify(html: str) -> str:
    html = re.sub(r"/static/([\w.]+)\?v=\d+", r"assets/\1", html)
    html = re.sub(r'(src|href)="/photo/(\d+)"', r'\1="img/\2.jpg"', html)
    html = html.replace('<script src="https://unpkg.com/htmx.org@2.0.3" defer></script>', "")
    # HTMX attributes and server forms → handled by proto.js
    html = re.sub(r'\s+hx-[\w-]+="[^"]*"', "", html)
    html = html.replace('action="/search"', 'action="index.html"')
    html = html.replace('href="/"', 'href="index.html"')
    scripts = '<script src="assets/results.js"></script>\n<script src="assets/proto.js"></script>'
    return html.replace("</body>", scripts + "\n</body>")


def main() -> None:
    s = get_settings()
    store = VectorStore(s.db_path)
    embedder = GemmaEmbedder(s.model_id, s.embed_dim)

    shutil.rmtree(OUT, ignore_errors=True)
    (OUT / "img").mkdir(parents=True)
    (OUT / "assets").mkdir()
    for f in ("style.css", "waves.js"):
        shutil.copy(STATIC / f, OUT / "assets" / f)
    shutil.copy(Path(__file__).parent / "proto.js", OUT / "assets" / "proto.js")

    used: set[int] = set()
    count = store.count()
    results = {}
    for q in QUERIES:
        hits = store.search(embedder.embed_query(q), TOP_K)
        for h in hits:
            save_image(store, h.id, used)
        results[q] = staticify(render("_results.html", q=q, results=hits, count=count))
        print(f"{q!r}: top score {hits[0].score:.2f}")

    samples = store.sample(3)
    for p in samples:
        save_image(store, p.id, used)

    ctx = {"count": count, "dim": s.embed_dim, "samples": samples}
    (OUT / "index.html").write_text(staticify(render("index.html", **ctx)))
    (OUT / "assets" / "results.js").write_text(
        "window.PRESETS = " + json.dumps(results, ensure_ascii=False) + ";\n"
    )
    size = sum(f.stat().st_size for f in OUT.rglob("*") if f.is_file())
    print(f"built {OUT} — {len(used)} photos, {size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
