"""Shared utilities."""

from __future__ import annotations

import re


def normalize_article_num(raw: str) -> int:
    """Normaliza un numero de articulo a int. Retorna 0 si no es valido."""
    cleaned = re.sub(r'[°ºª\s]', '', raw)
    try:
        return int(cleaned)
    except ValueError:
        return 0
