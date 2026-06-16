"""Wspólny klient HTTP: realistyczny UA, rate limiting, async."""
from __future__ import annotations

import asyncio
import logging

import httpx

from .config import REQUEST_DELAY_S, USER_AGENT

log = logging.getLogger(__name__)


def make_client(**kwargs) -> httpx.AsyncClient:
    """Tworzy asynchroniczny klient z domyślnym UA i follow_redirects."""
    headers = {"User-Agent": USER_AGENT}
    headers.update(kwargs.pop("headers", {}))
    return httpx.AsyncClient(
        headers=headers,
        timeout=kwargs.pop("timeout", 25.0),
        follow_redirects=kwargs.pop("follow_redirects", True),
        **kwargs,
    )


async def get_text(client: httpx.AsyncClient, url: str, **kwargs) -> str:
    """GET z rate limitingiem; zwraca tekst. Podnosi httpx.HTTPStatusError."""
    await asyncio.sleep(REQUEST_DELAY_S)
    r = await client.get(url, **kwargs)
    r.raise_for_status()
    return r.text


async def get_json(client: httpx.AsyncClient, url: str, **kwargs):
    """GET z rate limitingiem; zwraca sparsowany JSON."""
    await asyncio.sleep(REQUEST_DELAY_S)
    r = await client.get(url, **kwargs)
    r.raise_for_status()
    return r.json()
