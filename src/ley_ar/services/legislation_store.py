"""
Almacen de legislacion: carga los JSONs y permite buscar articulos por ID.
Mapea IDs del tipo "LCT_178" al texto completo del articulo.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

from ley_ar.utils import normalize_article_num

DATA_DIR = Path(__file__).parent.parent / "data" / "legislacion"

_LAW_FILES = {
    "LCT": "LCT.json",
    "LRT": "LRT.json",
    "LdE": "LdE.json",
    "LJT": "LJT.json",
    "LEY-25323": "ley-25323.json",
    "LEY-23345": "ley-23345.json",
    "LEY-25551": "ley-25551.json",
}

# Aliases para que el usuario pueda buscar con distintos nombres
_LAW_ALIASES = {
    "20744": "LCT",
    "ley 20744": "LCT",
    "ley 20.744": "LCT",
    "ley de contrato de trabajo": "LCT",
    "24557": "LRT",
    "ley 24557": "LRT",
    "ley 24.557": "LRT",
    "ley de riesgos del trabajo": "LRT",
    "24013": "LdE",
    "ley 24013": "LdE",
    "ley 24.013": "LdE",
    "ley de empleo": "LdE",
    "ley nacional de empleo": "LdE",
    "11544": "LJT",
    "ley 11544": "LJT",
    "ley 11.544": "LJT",
    "ley de jornada de trabajo": "LJT",
    "25323": "LEY-25323",
    "ley 25323": "LEY-25323",
    "ley 25.323": "LEY-25323",
    "23345": "LEY-23345",
    "ley 23345": "LEY-23345",
    "ley 23.345": "LEY-23345",
    "25551": "LEY-25551",
    "ley 25551": "LEY-25551",
    "ley 25.551": "LEY-25551",
}


class LegislationStore:

    def __init__(self, data_dir: str = None):
        self.dir = Path(data_dir) if data_dir else DATA_DIR
        self.articles: Dict[str, Dict] = {}
        self._load_all()

    def _load_all(self):
        for code, filename in _LAW_FILES.items():
            filepath = self.dir / filename
            if not filepath.exists():
                continue

            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            articles = data if isinstance(data, list) else data.get("articles", [])

            for a in articles:
                meta = a.get("metadata", {})
                raw_num = meta.get("article", "")
                num = normalize_article_num(raw_num)
                if num == 0:
                    continue

                art_id = f"{code}_{num}"
                self.articles[art_id] = {
                    "id": art_id,
                    "codigo": code,
                    "numero": num,
                    "codigo_nombre": meta.get("code", code),
                    "contenido": a.get("content", ""),
                    "capitulo": meta.get("chapter", ""),
                    "seccion": meta.get("section", ""),
                    "tags": meta.get("tags", []),
                }

    def _resolve_law(self, ley: str) -> str:
        """Resuelve aliases a codigo interno."""
        upper = ley.strip().upper()
        if upper in _LAW_FILES:
            return upper
        lower = ley.strip().lower()
        if lower in _LAW_ALIASES:
            return _LAW_ALIASES[lower]
        # Probar sin puntos
        no_dots = lower.replace(".", "")
        if no_dots in _LAW_ALIASES:
            return _LAW_ALIASES[no_dots]
        return ley.strip().upper()

    def get(self, ley: str, articulo: str) -> Dict | None:
        """Busca un articulo por ley + numero."""
        code = self._resolve_law(ley)
        num = normalize_article_num(articulo)
        art_id = f"{code}_{num}"
        return self.articles.get(art_id)

    def get_by_id(self, art_id: str) -> Dict | None:
        """Busca un articulo por ID directo (ej: 'LCT_245')."""
        return self.articles.get(art_id)

    def get_many(self, art_ids: List[str]) -> List[Dict]:
        return [a for aid in art_ids if (a := self.articles.get(aid))]

    def stats(self) -> Dict:
        codes: Dict[str, int] = {}
        for art in self.articles.values():
            code = art["codigo"]
            codes[code] = codes.get(code, 0) + 1
        return {"total": len(self.articles), "by_code": codes}
