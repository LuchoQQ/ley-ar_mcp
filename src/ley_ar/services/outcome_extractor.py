"""
Extrae el resultado (outcome) de un fallo judicial a partir de su sumario y texto.
Detecta si el fallo fue favorable, desfavorable, parcial, revocacion o settlement.
"""

from __future__ import annotations

import re
from typing import Optional, Tuple

# Patrones ordenados por especificidad (los mas especificos primero)
PATTERNS_FAVORABLE = [
    (r"\bhace?\s+lugar\b", 0.9),
    (r"\bhizo\s+lugar\b", 0.9),
    (r"\bprosper[ao]\b", 0.85),
    (r"\bse\s+admite\b", 0.85),
    (r"\bse\s+condena\b", 0.85),
    (r"\bcondena\s+a\b", 0.85),
    (r"\bcorresponde\s+(?:la\s+)?indemnizaci[oó]n\b", 0.8),
    (r"\bse\s+confirma\s+(?:la\s+)?sentencia\b", 0.7),
]

PATTERNS_DESFAVORABLE = [
    (r"\brechaz[ao]\b", 0.9),
    (r"\bse\s+rechaza\b", 0.9),
    (r"\bdesestim[ao]\b", 0.85),
    (r"\bno\s+hace?\s+lugar\b", 0.9),
    (r"\bimprocedente\b", 0.85),
    (r"\bno\s+corresponde\b", 0.8),
    (r"\bse\s+absuelve\b", 0.85),
]

PATTERNS_PARCIAL = [
    (r"\bhace?\s+lugar\s+parcialmente\b", 0.9),
    (r"\badmite\s+parcialmente\b", 0.9),
    (r"\bparcialmente\s+procedente\b", 0.85),
    (r"\bhace?\s+lugar\s+en\s+forma\s+parcial\b", 0.9),
]

PATTERNS_REVOCACION = [
    (r"\bse\s+revoca\b", 0.9),
    (r"\bse\s+deja\s+sin\s+efecto\b", 0.85),
    (r"\bse\s+modifica\s+(?:la\s+)?sentencia\b", 0.8),
]

PATTERNS_SETTLEMENT = [
    (r"\btransacci[oó]n\b", 0.85),
    (r"\bconciliaci[oó]n\b", 0.8),
    (r"\bacuerdo\s+(?:de\s+)?partes\b", 0.8),
    (r"\bhomolog[ao]\b", 0.75),
]

ALL_CATEGORIES = [
    ("parcial", PATTERNS_PARCIAL),  # Check parcial before favorable (more specific)
    ("favorable", PATTERNS_FAVORABLE),
    ("desfavorable", PATTERNS_DESFAVORABLE),
    ("revocacion", PATTERNS_REVOCACION),
    ("settlement", PATTERNS_SETTLEMENT),
]


def extract_outcome(sumario: str, texto: str = "") -> Optional[dict]:
    """Extrae el outcome de un fallo.

    Returns:
        dict con {outcome, confidence, source, pattern_matched} o None si indeterminado.
    """
    for source, content, base_boost in [("sumario", sumario, 1.0), ("texto", texto, 0.85)]:
        if not content:
            continue
        content_lower = content.lower()

        best_match = None
        best_score = 0

        for category, patterns in ALL_CATEGORIES:
            for pattern, base_confidence in patterns:
                match = re.search(pattern, content_lower)
                if match:
                    position_boost = 1.1 if match.start() < 200 else 1.0
                    score = base_confidence * base_boost * position_boost
                    if score > best_score:
                        best_score = score
                        best_match = {
                            "outcome": category,
                            "confidence": round(min(score, 1.0), 2),
                            "source": source,
                            "pattern_matched": pattern,
                        }

        if best_match:
            return best_match

    return None


def classify_court_level(record: dict) -> Tuple[str, float]:
    """Clasifica el nivel del tribunal y retorna (nivel, boost).

    Args:
        record: dict con campos del fallo (instancia, tipo-tribunal, titulo, etc.)

    Returns:
        (nivel_legible, boost_factor)
    """
    instancia = str(record.get("instancia", "")).upper()
    tipo_tribunal = str(record.get("tipo-tribunal", record.get("tipo_tribunal", ""))).upper()
    titulo = str(record.get("titulo", "")).lower()

    if tipo_tribunal == "CS" or "corte suprema" in titulo:
        return ("Corte Suprema de Justicia", 3.0)

    if instancia == "S" or "camara" in titulo or "superior tribunal" in titulo:
        return ("Camara de Apelaciones", 2.0)

    if instancia == "T" or tipo_tribunal in ("TR", "TL"):
        return ("Tribunal del Trabajo", 1.5)

    if instancia in ("C", "J") or "juzgado" in titulo:
        return ("Juzgado de Primera Instancia", 1.0)

    return ("Indeterminado", 1.0)
