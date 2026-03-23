from __future__ import annotations

import json
from pathlib import Path

CCT_PATH = Path(__file__).parent.parent / "data" / "cct" / "topes.json"

_cct_cache = None


def _load_ccts() -> dict:
    global _cct_cache
    if _cct_cache is None:
        if CCT_PATH.exists():
            with open(CCT_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            _cct_cache = {k: v for k, v in data.items() if not k.startswith("_")}
        else:
            _cct_cache = {}
    return _cct_cache


def consultar_cct(cct_id: str = None) -> dict:
    """Consulta datos de convenios colectivos de trabajo y sus topes indemnizatorios (art. 245 LCT).

    Sin parametros devuelve todos los CCTs disponibles.
    Con cct_id devuelve el detalle de un CCT especifico.

    Args:
        cct_id: Numero del CCT (ej: "130/75"). Si se omite, lista todos los disponibles.
    """
    ccts = _load_ccts()

    if cct_id:
        data = ccts.get(cct_id)
        if not data:
            return {
                "error": f"CCT {cct_id} no encontrado",
                "disponibles": [
                    {"cct": k, "nombre": v["nombre"]}
                    for k, v in ccts.items()
                ],
            }
        return {
            "cct": cct_id,
            **data,
            "nota_tope": (
                f"Art. 245 LCT: la base de calculo no puede exceder 3 veces este tope "
                f"(${data['tope_245'] * 3:,.0f}). Si la mejor remuneracion es menor, "
                f"no se aplica reduccion."
            ),
        }

    return {
        "convenios": [
            {
                "cct": k,
                "nombre": v["nombre"],
                "sindicato": v["sindicato"],
                "tope_245": v["tope_245"],
                "tope_245_3x": v["tope_245"] * 3,
                "vigencia_desde": v["vigencia_desde"],
            }
            for k, v in ccts.items()
        ],
        "total": len(ccts),
        "nota": "El tope del art. 245 LCT limita la base de calculo de la indemnizacion por antiguedad. La remuneracion no puede exceder 3 veces el tope del CCT aplicable.",
    }
