from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import Settings, get_settings
from app.embedder import Embedder, GemmaEmbedder
from app.store import VectorStore

BASE = Path(__file__).parent
templates = Jinja2Templates(directory=BASE / "templates")


def asset(path: str) -> str:
    # Version static URLs by mtime so browsers never keep a stale CSS/JS after an edit.
    return f"/static/{path}?v={int((BASE / 'static' / path).stat().st_mtime)}"


templates.env.globals["asset"] = asset
templates.env.globals["app_name"] = get_settings().app_name

_embedder: Embedder | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    app.state.store = VectorStore(s.db_path)
    yield


app = FastAPI(title=get_settings().app_name, lifespan=lifespan)
app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")


def get_store(request: Request) -> VectorStore:
    return request.app.state.store


SettingsDep = Annotated[Settings, Depends(get_settings)]


def get_embedder(s: SettingsDep) -> Embedder:
    # Lazy: the model loads on first search, so the site boots instantly.
    global _embedder
    if _embedder is None:
        _embedder = GemmaEmbedder(s.model_id, s.embed_dim)
    return _embedder


StoreDep = Annotated[VectorStore, Depends(get_store)]
EmbedderDep = Annotated[Embedder, Depends(get_embedder)]


@app.get("/", response_class=HTMLResponse)
def home(request: Request, store: StoreDep, s: SettingsDep):
    return templates.TemplateResponse(
        request,
        "index.html",
        {"count": store.count(), "dim": s.embed_dim, "samples": store.sample(3)},
    )


@app.get("/search", response_class=HTMLResponse)
def search(
    request: Request,
    store: StoreDep,
    embedder: EmbedderDep,
    s: SettingsDep,
    q: str = "",
):
    results = store.search(embedder.embed_query(q.strip()), s.top_k) if q.strip() else []
    # HTMX requests get just the results grid; full page loads get the whole page.
    template = "_results.html" if request.headers.get("HX-Request") else "index.html"
    return templates.TemplateResponse(
        request,
        template,
        {
            "q": q,
            "results": results,
            "count": store.count(),
            "dim": s.embed_dim,
            "samples": store.sample(3),
        },
    )


@app.get("/photo/{photo_id}")
def photo(photo_id: int, store: StoreDep):
    # Serve only paths that are in the index — never arbitrary filesystem paths.
    p = store.get(photo_id)
    if p is None or not Path(p.path).is_file():
        raise HTTPException(404)
    return FileResponse(p.path)
