"""Vercel entrypoint – re-export FastAPI app."""
from app.main import app

__all__ = ["app"]
