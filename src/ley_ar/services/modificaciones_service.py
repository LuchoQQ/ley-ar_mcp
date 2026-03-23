"""
Servicio de solo lectura que carga modificaciones.json
y permite consultar el historial de cambios de un articulo.

No interpreta ni filtra. Solo reporta hechos normativos.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

DATA_DIR = Path(__file__).parent.parent / "data"
DEFAULT_PATH = DATA_DIR / "modificaciones.json"


class ModificacionesService:

    def __init__(self, path: str = None):
        filepath = Path(path) if path else DEFAULT_PATH
        self.modificaciones: Dict[str, List[Dict]] = {}
        if filepath.exists():
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.modificaciones = {
                k: v for k, v in data.items() if not k.startswith("_")
            }

    def get(self, article_id: str) -> List[Dict]:
        """Retorna lista de eventos para un articulo. Lista vacia si no tiene."""
        return self.modificaciones.get(article_id, [])

    def tiene_modificaciones(self, article_id: str) -> bool:
        return article_id in self.modificaciones

    def ultimo_evento(self, article_id: str) -> Optional[Dict]:
        eventos = self.get(article_id)
        return eventos[-1] if eventos else None

    def fue_derogado(self, article_id: str) -> bool:
        """True si el ultimo evento es una derogacion."""
        ultimo = self.ultimo_evento(article_id)
        return ultimo is not None and ultimo.get("tipo") == "derogacion"

    def fue_sustituido(self, article_id: str) -> bool:
        """True si el ultimo evento es una sustitucion."""
        ultimo = self.ultimo_evento(article_id)
        return ultimo is not None and ultimo.get("tipo") == "sustitucion"

    def annotate(self, article_id: str) -> Optional[Dict]:
        """Genera un resumen para adjuntar al output de las tools.
        Retorna None si no hay modificaciones.
        """
        eventos = self.get(article_id)
        if not eventos:
            return None
        ultimo = eventos[-1]
        return {
            "modificado": True,
            "ultimo_evento": ultimo["tipo"],
            "norma": f"{ultimo['norma']} art. {ultimo['articulo']}",
            "fecha": ultimo["fecha"],
            "bo": ultimo.get("bo", ""),
            "descripcion": ultimo.get("descripcion", ""),
            "total_eventos": len(eventos),
        }

    def annotate_many(self, article_ids: List[str]) -> Dict[str, Dict]:
        """Genera anotaciones para multiples articulos.
        Solo incluye los que tienen modificaciones.
        """
        result = {}
        for aid in article_ids:
            ann = self.annotate(aid)
            if ann:
                result[aid] = ann
        return result
