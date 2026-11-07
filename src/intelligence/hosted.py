"""Shared public-market data only. Never export a local database or broker files."""
from threading import Lock
from .refresh import refresh_sources

_LOCK=Lock()


def refresh_public(root):
    # Serialize source updates across visitor sessions in the hosted process.
    if not _LOCK.acquire(blocking=False):
        return {'acquired':0,'errors':['Un aggiornamento è già in corso; rileggi fra poco.']}
    try:
        return refresh_sources(root)
    finally:
        _LOCK.release()
