"""
Buscador de jurisprudencia: dado descriptores ponderados,
encuentra los fallos mas relevantes del dataset.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Dict, List, Tuple

from ley_ar.services.outcome_extractor import classify_court_level, extract_outcome

DATA_DIR = Path(__file__).parent.parent / "data"
DATASET_PATH = DATA_DIR / "jurisprudencia" / "jurisprudencia_laboral.jsonl"


class JurisprudenciaSearch:

    def __init__(self, dataset_path: str = None):
        path = Path(dataset_path) if dataset_path else DATASET_PATH
        self.records = []
        self.descriptor_index = {}
        self.path_to_elegidos = {}
        self.sumario_index: dict[str, int] = {}
        self._load(path)

    def _is_laboral(self, materia: str) -> bool:
        """Filtra solo fallos de materia laboral."""
        if not materia:
            return False
        return "laboral" in materia.lower()

    def _recency_boost(self, fecha: str) -> float:
        """Boost por recencia: fallos recientes rankean significativamente mas alto."""
        if not fecha or len(fecha) < 4:
            return 0.3
        try:
            year = int(fecha[:4])
        except ValueError:
            return 0.3
        if year >= 2020:
            return 2.0
        if year >= 2015:
            return 1.5
        if year >= 2010:
            return 1.0
        if year >= 2005:
            return 0.6
        return 0.3

    def _load(self, path: Path):
        with open(path, "r", encoding="utf-8") as f:
            for i, line in enumerate(f):
                if not line.strip():
                    continue
                record = json.loads(line)

                materia = record.get("materia", "")
                if not self._is_laboral(materia):
                    continue

                elegidos = set()
                desc = record.get("descriptores")
                if desc and isinstance(desc, dict):
                    descriptor_list = desc.get("descriptor", [])
                    if isinstance(descriptor_list, dict):
                        descriptor_list = [descriptor_list]
                    for d in descriptor_list:
                        if not isinstance(d, dict):
                            continue
                        term = (d.get("elegido") or {}).get("termino", "").strip().lower()
                        pref = (d.get("preferido") or {}).get("termino", "").strip().lower()
                        if term:
                            elegidos.add(term)
                            if pref:
                                if pref not in self.path_to_elegidos:
                                    self.path_to_elegidos[pref] = set()
                                self.path_to_elegidos[pref].add(term)

                sumario = record.get("sumario", "")
                sumario = re.sub(r'\[\[/?[^\]]*\]\]', '', sumario).strip()

                texto = record.get("texto", "")
                texto = re.sub(r'\[\[/?[^\]]*\]\]', '', texto).strip()

                self.records.append({
                    "idx": i,
                    "numero_sumario": str(record.get("numero-sumario", "")),
                    "titulo": str(record.get("titulo", "")),
                    "caratula": str(record.get("caratula", "")),
                    "sumario": sumario,
                    "texto": texto,
                    "fecha": record.get("fecha", ""),
                    "provincia": record.get("provincia", ""),
                    "instancia": record.get("instancia", ""),
                    "tipo_tribunal": record.get("tipo-tribunal", ""),
                    "elegidos": elegidos,
                })

                record_idx = len(self.records) - 1
                ns = self.records[record_idx]["numero_sumario"]
                if ns:
                    self.sumario_index[ns] = record_idx

                for e in elegidos:
                    if e not in self.descriptor_index:
                        self.descriptor_index[e] = []
                    self.descriptor_index[e].append(record_idx)

    def search(
        self,
        descriptor_scores: List[Tuple[str, float]],
        top_k: int = 5,
        min_overlap: int = 1,
        jurisdiccion: str = None,
    ) -> List[Dict]:
        score_map = {}
        for desc, score in descriptor_scores:
            desc_lower = desc.lower()
            score_map[desc_lower] = max(score_map.get(desc_lower, 0), score)

        # Expandir con equivalentes jerarquicos
        expanded_map = dict(score_map)
        equivalence_groups: Dict[str, set] = {}
        for desc, score in score_map.items():
            for path, elegidos in self.path_to_elegidos.items():
                if desc in elegidos:
                    for equiv in elegidos:
                        if equiv not in equivalence_groups:
                            equivalence_groups[equiv] = set()
                        equivalence_groups[equiv].update(elegidos & set(score_map.keys()))
                        if equiv not in expanded_map:
                            expanded_map[equiv] = score

        candidate_idxs = set()
        for desc in expanded_map:
            for idx in self.descriptor_index.get(desc, []):
                candidate_idxs.add(idx)

        scored = []
        for idx in candidate_idxs:
            record = self.records[idx]

            if jurisdiccion and record["provincia"].lower() != jurisdiccion.lower():
                continue

            matching_descs = []
            total_score = 0.0

            for elegido in record["elegidos"]:
                if elegido in expanded_map:
                    desc_score = expanded_map[elegido]
                    matching_descs.append(elegido)
                    # Also include equivalent query-side descriptors
                    if elegido in equivalence_groups:
                        for equiv in equivalence_groups[elegido]:
                            if equiv not in matching_descs:
                                matching_descs.append(equiv)
                    n_fallos = len(self.descriptor_index.get(elegido, []))
                    specificity = 1.0 / math.log(2 + n_fallos)
                    total_score += desc_score * specificity

            if len(matching_descs) < min_overlap:
                continue

            boost = self._recency_boost(record["fecha"])
            nivel_tribunal, court_boost = classify_court_level(record)
            final_score = total_score * boost * court_boost

            outcome = extract_outcome(record["sumario"], record["texto"])

            fallo = {
                "numero_sumario": record["numero_sumario"],
                "titulo": record["titulo"],
                "caratula": record["caratula"],
                "sumario": record["sumario"],
                "texto": record["texto"],
                "fecha": record["fecha"],
                "provincia": record["provincia"],
                "instancia": record.get("instancia", ""),
                "tipo_tribunal": record.get("tipo_tribunal", ""),
                "nivel_tribunal": nivel_tribunal,
                "outcome": outcome,
                "descriptors_overlap": sorted(matching_descs),
                "overlap_count": len(matching_descs),
                "relevance_score": round(final_score, 2),
            }

            scored.append(fallo)

        scored.sort(key=lambda x: (x["relevance_score"], x["fecha"]), reverse=True)

        # Deduplicar por caratula
        seen = set()
        deduped = []
        for s in scored:
            key = s["caratula"].strip().lower()
            if key not in seen:
                seen.add(key)
                deduped.append(s)

        return deduped[:top_k]

    def search_by_caratula(
        self,
        texto: str,
        top_k: int = 5,
        jurisdiccion: str = None,
    ) -> List[Dict]:
        """Busca fallos por texto en la caratula (nombre del caso).

        Busqueda case-insensitive por substring. Util para buscar fallos
        emblematicos por nombre (ej: "Vizzoti", "Aquino", "Madorrán").

        Args:
            texto: Texto a buscar en la caratula
            top_k: Cantidad maxima de resultados
            jurisdiccion: Filtro opcional por provincia
        """
        texto_lower = texto.lower()
        results = []

        for record in self.records:
            if texto_lower not in record["caratula"].lower():
                continue

            if jurisdiccion and record["provincia"].lower() != jurisdiccion.lower():
                continue

            nivel_tribunal, _ = classify_court_level(record)
            outcome = extract_outcome(record["sumario"], record["texto"])

            results.append({
                "numero_sumario": record["numero_sumario"],
                "titulo": record["titulo"],
                "caratula": record["caratula"],
                "sumario": record["sumario"],
                "texto": record["texto"],
                "fecha": record["fecha"],
                "provincia": record["provincia"],
                "instancia": record.get("instancia", ""),
                "tipo_tribunal": record.get("tipo_tribunal", ""),
                "nivel_tribunal": nivel_tribunal,
                "outcome": outcome,
                "descriptores": sorted(record["elegidos"]),
            })

        # Ordenar por fecha descendente (fallos más recientes primero)
        results.sort(key=lambda x: x.get("fecha", ""), reverse=True)
        return results[:top_k]

    def get_by_id(self, numero_sumario: str) -> dict | None:
        """Busca un fallo especifico por su numero de sumario.

        Args:
            numero_sumario: Identificador unico del fallo
        """
        idx = self.sumario_index.get(numero_sumario)
        if idx is None:
            return None
        record = self.records[idx]
        nivel_tribunal, _ = classify_court_level(record)
        outcome = extract_outcome(record["sumario"], record["texto"])
        return {
            "numero_sumario": record["numero_sumario"],
            "titulo": record["titulo"],
            "caratula": record["caratula"],
            "sumario": record["sumario"],
            "texto": record["texto"],
            "fecha": record["fecha"],
            "provincia": record["provincia"],
            "instancia": record.get("instancia", ""),
            "tipo_tribunal": record.get("tipo_tribunal", ""),
            "nivel_tribunal": nivel_tribunal,
            "outcome": outcome,
            "descriptores": sorted(record["elegidos"]),
        }
