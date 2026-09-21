"""Stage 3: turn text into vectors.

An embedding model is not the chat model and does not do the same job:

    chat model        text -> text        ("you spent 5,000 rupees on hotels")
    embedding model   text -> numbers     ([0.0234, -0.891, 0.445, ...])

Those numbers place a piece of text in a space where nearby means "means
something similar". That is what lets a search for "cab expense" find a
receipt that says "taxi fare", with no shared words at all.

Which model, and why this one
-----------------------------
all-MiniLM-L6-v2, run through ONNX Runtime on the CPU. 384 dimensions,
around 80 MB, a few hundred megabytes of RAM while running.

The obvious alternative, sentence-transformers, pulls in PyTorch: 554 MB for
torch plus 248 MB for triton before a single model is downloaded. On a laptop
with about 1.5 GB of free memory that is the wrong trade for the same MiniLM
weights this runs directly.

This module is the only place the application knows which model is in use.
Everything else asks for vectors and is told how many dimensions they have.
The model is named in .env, and swapping it means changing that name and
re-indexing -- never editing code in several places.
"""
import logging
import threading

from config import settings

log = logging.getLogger("uvicorn.error")

# name in .env -> (loader, dimensions). Adding a model means adding a row.
_MODELS: dict[str, int] = {
    "onnx-minilm-l6-v2": 384,
}

_lock = threading.Lock()
_function = None      # the loaded embedding function, or None


class EmbeddingError(Exception):
    """Raised when text cannot be embedded, with a message worth showing."""


def model_name() -> str:
    return settings.EMBED_MODEL


def dimensions() -> int:
    """How many numbers are in one vector.

    Needed before any text is embedded: a collection is created with a fixed
    width, and vectors of a different width cannot be mixed into it.
    """
    try:
        return _MODELS[settings.EMBED_MODEL]
    except KeyError:
        raise EmbeddingError(
            f"Unknown EMBED_MODEL {settings.EMBED_MODEL!r}. "
            f"Known models: {', '.join(sorted(_MODELS))}."
        )


def _load():
    """Load the model once, on first use.

    Deliberately not at import: the backend should start instantly and use no
    extra memory for someone who never touches search.
    """
    global _function
    if _function is not None:
        return _function

    with _lock:
        if _function is not None:       # another thread got here first
            return _function
        if settings.EMBED_MODEL not in _MODELS:
            raise EmbeddingError(
                f"Unknown EMBED_MODEL {settings.EMBED_MODEL!r}. "
                f"Known models: {', '.join(sorted(_MODELS))}."
            )
        try:
            from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2
            log.info("embeddings: loading %s (first use downloads ~80 MB)",
                     settings.EMBED_MODEL)
            _function = ONNXMiniLM_L6_V2()
        except Exception as exc:
            raise EmbeddingError(
                f"Could not load the embedding model ({type(exc).__name__}). "
                "Semantic search is unavailable until this is fixed."
            )
    return _function


def available() -> bool:
    """Whether embedding works right now, without raising."""
    try:
        _load()
        return True
    except EmbeddingError:
        return False


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts. Order of the result matches the input."""
    if not texts:
        return []
    if any(not isinstance(t, str) for t in texts):
        raise EmbeddingError("Only text can be embedded.")

    # Empty strings produce a meaningless vector and waste a forward pass;
    # they are embedded as a single space so positions still line up.
    prepared = [t if t.strip() else " " for t in texts]

    function = _load()
    width = dimensions()
    vectors: list[list[float]] = []

    # Batched so a long document cannot allocate one enormous array.
    for start in range(0, len(prepared), settings.EMBED_BATCH_SIZE):
        batch = prepared[start:start + settings.EMBED_BATCH_SIZE]
        try:
            produced = function(batch)
        except Exception as exc:
            raise EmbeddingError(f"Embedding failed ({type(exc).__name__}).")
        for vector in produced:
            values = [float(v) for v in vector]
            if len(values) != width:
                raise EmbeddingError(
                    f"Model returned {len(values)} dimensions, expected {width}."
                )
            vectors.append(values)

    return vectors


def embed_query(text: str) -> list[float]:
    """Embed one search query."""
    if not text or not text.strip():
        raise EmbeddingError("An empty query cannot be searched for.")
    return embed_texts([text])[0]
