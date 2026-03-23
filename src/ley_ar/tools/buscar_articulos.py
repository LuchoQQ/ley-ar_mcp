from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

from ley_ar.services.legislation_store import LegislationStore

_SITUACIONES_PATH = Path(__file__).parent.parent / "data" / "situaciones_legales.json"
_situaciones_cache: Optional[Dict] = None


def _load_situaciones() -> Dict:
    global _situaciones_cache
    if _situaciones_cache is not None:
        return _situaciones_cache
    with open(_SITUACIONES_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    # Excluir _meta
    _situaciones_cache = {k: v for k, v in data.items() if not k.startswith("_")}
    return _situaciones_cache


def _resolve_herencia(situaciones: Dict, situacion_id: str) -> List[Dict]:
    """Resuelve la cadena de herencia y devuelve los articulos primarios acumulados."""
    sit = situaciones.get(situacion_id)
    if not sit:
        return []

    articulos = list(sit.get("articulos_primarios", []))

    hereda = sit.get("hereda")
    if hereda and hereda in situaciones:
        heredados = _resolve_herencia(situaciones, hereda)
        # Agregar heredados que no esten ya (por ID)
        ids_existentes = {a["id"] for a in articulos}
        for art in heredados:
            if art["id"] not in ids_existentes:
                articulos.append(art)

    return articulos


def buscar_articulos(
    store: LegislationStore,
    situacion: str,
    condiciones: list = None,
    mod_service=None,
) -> dict:
    """Devuelve los articulos de legislacion laboral aplicables a una situacion concreta.

    Lookup determinista basado en un mapeo experto de situaciones legales a articulos.
    Cada articulo incluye su rol especifico en la situacion.

    Args:
        situacion: Tipo de situacion laboral
        condiciones: Circunstancias que activan articulos adicionales
    """
    situaciones = _load_situaciones()

    # Si no se pasa situacion, devolver el catalogo
    if not situacion or situacion == "listar":
        catalogo = []
        for sid, data in situaciones.items():
            entry = {
                "id": sid,
                "nombre": data["nombre"],
                "descripcion": data["descripcion"],
                "categoria": data.get("categoria", ""),
            }
            conds = data.get("condicionales", {})
            if conds:
                entry["condiciones_disponibles"] = list(conds.keys())
            catalogo.append(entry)
        return {
            "tipo": "catalogo",
            "situaciones": catalogo,
            "total": len(catalogo),
            "instrucciones": "Selecciona una o mas situaciones y sus condiciones para obtener los articulos aplicables.",
        }

    # Puede recibir multiples situaciones separadas por coma
    situacion_ids = [s.strip() for s in situacion.split(",")]
    condiciones = condiciones or []

    all_articulos = []  # Lista ordenada
    seen_ids = set()
    situaciones_procesadas = []
    notas_todas = []
    relacionadas_todas = set()

    for sit_id in situacion_ids:
        sit = situaciones.get(sit_id)
        if not sit:
            # Buscar por nombre parcial
            matches = [
                (k, v) for k, v in situaciones.items()
                if sit_id.lower() in k.lower() or sit_id.lower() in v["nombre"].lower()
            ]
            if len(matches) == 1:
                sit_id, sit = matches[0]
            elif matches:
                return {
                    "error": f"Situacion '{sit_id}' ambigua. Coincidencias: {[m[0] for m in matches]}",
                    "sugerencia": "Usa el ID exacto de la situacion.",
                }
            else:
                return {
                    "error": f"Situacion '{sit_id}' no encontrada.",
                    "situaciones_disponibles": list(situaciones.keys()),
                }

        situaciones_procesadas.append({
            "id": sit_id,
            "nombre": sit["nombre"],
        })

        # Articulos primarios (con herencia)
        primarios = _resolve_herencia(situaciones, sit_id)
        for art in primarios:
            if art["id"] not in seen_ids:
                seen_ids.add(art["id"])
                all_articulos.append({
                    **art,
                    "tipo": "primario",
                    "situacion": sit_id,
                })

        # Articulos condicionales
        condicionales = sit.get("condicionales", {})
        for cond in condiciones:
            if cond in condicionales:
                for art in condicionales[cond].get("articulos", []):
                    if art["id"] not in seen_ids:
                        seen_ids.add(art["id"])
                        all_articulos.append({
                            **art,
                            "tipo": "condicional",
                            "condicion": cond,
                            "descripcion_condicion": condicionales[cond].get("descripcion", ""),
                            "situacion": sit_id,
                        })

        # Notas y relacionadas
        notas_todas.extend(sit.get("notas", []))
        relacionadas_todas.update(sit.get("relacionadas", []))

    # Quitar situaciones ya procesadas de las relacionadas
    relacionadas_todas -= set(situacion_ids)

    # Enriquecer con texto completo del articulo
    articulos_enriquecidos = []
    for art_entry in all_articulos:
        art_data = store.get_by_id(art_entry["id"])
        enriched = {
            "id": art_entry["id"],
            "rol": art_entry["rol"],
            "tipo": art_entry["tipo"],
        }
        if art_entry["tipo"] == "condicional":
            enriched["condicion"] = art_entry["condicion"]

        if art_data:
            enriched["ley"] = art_data["codigo_nombre"]
            enriched["articulo"] = str(art_data["numero"])
            enriched["texto"] = art_data["contenido"]
            enriched["capitulo"] = art_data.get("capitulo", "")
        else:
            enriched["texto"] = None
            enriched["advertencia"] = f"Articulo {art_entry['id']} no encontrado en la base de legislacion"

        if mod_service:
            ann = mod_service.annotate(art_entry["id"])
            if ann:
                enriched["modificaciones"] = ann

        articulos_enriquecidos.append(enriched)

    # Condiciones disponibles no usadas (para que el LLM sepa que puede refinar)
    condiciones_no_usadas = {}
    for sit_id in situacion_ids:
        sit = situaciones.get(sit_id, {})
        for cond_id, cond_data in sit.get("condicionales", {}).items():
            if cond_id not in condiciones:
                condiciones_no_usadas[cond_id] = cond_data.get("descripcion", "")

    result = {
        "situaciones": situaciones_procesadas,
        "condiciones_aplicadas": condiciones,
        "articulos": articulos_enriquecidos,
        "total_articulos": len(articulos_enriquecidos),
        "notas": notas_todas,
    }

    if condiciones_no_usadas:
        result["condiciones_disponibles"] = condiciones_no_usadas

    if relacionadas_todas:
        result["situaciones_relacionadas"] = sorted(relacionadas_todas)

    return result
