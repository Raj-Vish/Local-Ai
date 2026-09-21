"""Every address, path and secret the application needs.

Nothing else in the codebase reads os.environ or hard-codes a URL. Moving to
the college server should mean editing .env and nothing else.
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60
    STORAGE_ROOT: str
    MAX_UPLOAD_MB: int = 10
    CORS_ORIGINS: str = "http://localhost:5173"

    # --- Stage 1: document text extraction -------------------------------
    # OCR is optional: without Tesseract the backend still starts and digital
    # PDFs still read, so a machine that has not set it up is not blocked.
    OCR_ENABLED: bool = True
    OCR_LANG: str = "eng"
    # 200 dpi is the point where Tesseract stops gaining accuracy on receipts
    # and starts costing real memory. This laptop has little to spare.
    OCR_DPI: int = 200
    # Tesseract page segmentation. 4 = "a single column of text of variable
    # sizes", which is what a receipt is. The default (3) hunts for separate
    # blocks and splits the item column away from the amount column, so
    # "Masala Dosa" and "360.00" stop sharing a line -- exactly the pairing
    # that field extraction will depend on.
    OCR_PSM: int = 4
    EXTRACT_MAX_PAGES: int = 20
    # Below this many characters a PDF is treated as a picture, not a document.
    EXTRACT_MIN_CHARS: int = 40
    EXTRACT_TIMEOUT_SECONDS: int = 180

    # --- Stage 2: chunking ------------------------------------------------
    # Characters, not tokens: the text here is receipts and invoices, and a
    # character budget is something a person can reason about without needing
    # a tokeniser to tell them what a chunk will contain.
    CHUNK_SIZE_CHARS: int = 1000
    CHUNK_OVERLAP_CHARS: int = 150
    # A trailing remainder smaller than this is merged into the chunk before
    # it rather than left as a stub that retrieves badly.
    CHUNK_MIN_CHARS: int = 80

    # --- Stage 3/4: embeddings and the vector store -----------------------
    # Named here rather than hard-coded, so swapping the model is a config
    # change plus a re-index. See services/embeddings.py for why MiniLM.
    EMBED_MODEL: str = "onnx-minilm-l6-v2"
    EMBED_BATCH_SIZE: int = 16
    # Persisted on disk so restarting the backend does not lose the index.
    CHROMA_PATH: str = ""
    CHROMA_COLLECTION: str = "document_chunks"
    RAG_TOP_K: int = 5
    RAG_MAX_TOP_K: int = 20

    # --- Stage 7: the teammate's language service -------------------------
    # Blank by default and blank in the repo: nothing about this machine
    # assumes a model is available, and no host is hard-coded anywhere. Set
    # this to the address of whoever is running Ollama.
    LLM_URL: str = ""
    LLM_MODEL: str = "qwen2.5:1.5b"
    LLM_TIMEOUT_SECONDS: int = 120

    @property
    def cors_origins(self) -> list[str]:
        # A browser matches the Origin header exactly, so these must be full
        # origins ("http://localhost:5173"), never a bare host or a trailing slash.
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def chroma_path(self) -> str:
        """Where the vector index lives. Defaults beside the uploaded files."""
        from pathlib import Path
        if self.CHROMA_PATH:
            return self.CHROMA_PATH
        return str(Path(self.STORAGE_ROOT).parent / "chroma")

    @property
    def max_upload_bytes(self) -> int:
        return self.MAX_UPLOAD_MB * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    # Cached so the .env file is read once per process rather than per request.
    return Settings()


settings = get_settings()
