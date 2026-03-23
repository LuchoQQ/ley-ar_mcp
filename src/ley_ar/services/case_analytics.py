"""
Analytics sobre jurisprudencia: tasa de exito, estadisticas por jurisdiccion,
deteccion de doctrina contradictoria, evolucion temporal.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Optional, Tuple

from ley_ar.services.outcome_extractor import extract_outcome
from ley_ar.services.juris_search import JurisprudenciaSearch


class CaseAnalytics:

    def __init__(self, juris: JurisprudenciaSearch):
        self.juris = juris

    def analizar_caso(
        self,
        descriptor_scores: List[Tuple[str, float]],
        jurisdiccion: str = None,
        min_overlap: int = 1,
    ) -> dict:
        """Analiza estadisticas de jurisprudencia para un caso."""
        all_fallos = self.juris.search(
            descriptor_scores,
            top_k=500,
            min_overlap=min_overlap,
            jurisdiccion=jurisdiccion,
        )

        if not all_fallos:
            return {
                "n_casos_analizados": 0,
                "mensaje": "No se encontraron fallos con los descriptores del caso.",
            }

        favorable = 0
        desfavorable = 0
        parcial = 0
        indeterminado = 0
        por_jurisdiccion = defaultdict(lambda: {"favorable": 0, "desfavorable": 0, "parcial": 0, "total": 0})
        por_periodo = defaultdict(lambda: {"favorable": 0, "desfavorable": 0, "total": 0})
        alertas = []

        for fallo in all_fallos:
            outcome = extract_outcome(fallo.get("sumario", ""), fallo.get("texto", ""))
            prov = fallo.get("provincia", "Desconocida")

            if outcome:
                cat = outcome["outcome"]
                if cat in ("favorable", "revocacion"):
                    favorable += 1
                    por_jurisdiccion[prov]["favorable"] += 1
                elif cat == "desfavorable":
                    desfavorable += 1
                    por_jurisdiccion[prov]["desfavorable"] += 1
                elif cat == "parcial":
                    parcial += 1
                    por_jurisdiccion[prov]["favorable"] += 1
                elif cat == "settlement":
                    pass
                else:
                    indeterminado += 1
            else:
                indeterminado += 1

            por_jurisdiccion[prov]["total"] += 1

            fecha = fallo.get("fecha", "")
            if fecha and len(fecha) >= 4:
                try:
                    year = int(fecha[:4])
                    if year >= 2020:
                        periodo = "2020-presente"
                    elif year >= 2015:
                        periodo = "2015-2019"
                    elif year >= 2010:
                        periodo = "2010-2014"
                    else:
                        periodo = "pre-2010"

                    if outcome:
                        cat = outcome["outcome"]
                        if cat in ("favorable", "revocacion", "parcial"):
                            por_periodo[periodo]["favorable"] += 1
                        elif cat == "desfavorable":
                            por_periodo[periodo]["desfavorable"] += 1
                    por_periodo[periodo]["total"] += 1
                except ValueError:
                    pass

        total_con_outcome = favorable + desfavorable + parcial
        tasa_exito = round(favorable / total_con_outcome * 100, 1) if total_con_outcome > 0 else None

        stats_jurisdiccion = {}
        for prov, stats in sorted(por_jurisdiccion.items(), key=lambda x: x[1]["total"], reverse=True):
            total_prov = stats["favorable"] + stats["desfavorable"]
            stats_jurisdiccion[prov] = {
                "tasa_exito": round(stats["favorable"] / total_prov * 100, 1) if total_prov > 0 else None,
                "n_casos": stats["total"],
                "favorable": stats["favorable"],
                "desfavorable": stats["desfavorable"],
            }

        tendencia = {}
        for periodo in ["pre-2010", "2010-2014", "2015-2019", "2020-presente"]:
            if periodo in por_periodo:
                stats = por_periodo[periodo]
                total_p = stats["favorable"] + stats["desfavorable"]
                tendencia[periodo] = {
                    "tasa_exito": round(stats["favorable"] / total_p * 100, 1) if total_p > 0 else None,
                    "n_casos": stats["total"],
                }

        # Detectar cambio de tendencia
        periodos_keys = ["pre-2010", "2010-2014", "2015-2019", "2020-presente"]
        tasas_por_periodo = []
        for p in periodos_keys:
            if p in tendencia and tendencia[p]["tasa_exito"] is not None:
                tasas_por_periodo.append((p, tendencia[p]["tasa_exito"]))

        if len(tasas_por_periodo) >= 2:
            ultimo = tasas_por_periodo[-1]
            penultimo = tasas_por_periodo[-2]
            diff = ultimo[1] - penultimo[1]
            if abs(diff) > 15:
                direction = "aumento" if diff > 0 else "disminuyo"
                alertas.append(
                    f"Cambio de tendencia: la tasa de exito {direction} de {penultimo[1]}% ({penultimo[0]}) a {ultimo[1]}% ({ultimo[0]})"
                )

        # Detectar doctrina contradictoria
        for prov, stats in stats_jurisdiccion.items():
            if stats["favorable"] >= 2 and stats["desfavorable"] >= 2:
                alertas.append(
                    f"Doctrina dividida en {prov}: {stats['favorable']} fallos favorables vs {stats['desfavorable']} desfavorables"
                )

        result = {
            "n_casos_analizados": len(all_fallos),
            "n_con_outcome_detectable": total_con_outcome,
            "n_indeterminados": indeterminado,
            "tasa_exito_general": tasa_exito,
            "desglose": {
                "favorable": favorable,
                "desfavorable": desfavorable,
                "parcial": parcial,
            },
            "por_jurisdiccion": stats_jurisdiccion,
            "tendencia_temporal": tendencia,
            "alertas": alertas,
            "metodologia": {
                "clasificacion_outcomes": (
                    "Los resultados de cada fallo se clasifican mediante patrones "
                    "de texto (regex) sobre el sumario. Este metodo tiene limitaciones: "
                    "fallos con resultados parciales o mixtos pueden clasificarse "
                    "incorrectamente. La tasa de exito refleja la proporcion de fallos "
                    "que nuestro clasificador automatico interpreto como favorables, "
                    "NO la probabilidad real de ganar un caso similar."
                ),
                "muestra": (
                    f"Sobre {len(all_fallos)} fallos encontrados, {total_con_outcome} "
                    f"tuvieron un resultado clasificable ({indeterminado} no pudieron clasificarse). "
                    "La muestra esta sesgada hacia CABA y Buenos Aires."
                ),
                "limitaciones": [
                    "No es una prediccion de resultado judicial",
                    "El clasificador de resultados es heuristico (basado en patrones de texto)",
                    "Fallos con resultados mixtos o parciales pueden clasificarse incorrectamente",
                    "La base de jurisprudencia tiene mayor cobertura en CABA y Buenos Aires",
                    "Los fallos se ponderan por recencia (post-2020 pesan mas) y jerarquia del tribunal",
                ],
            },
        }

        return result

    @staticmethod
    def costo_beneficio(
        monto_inmediatos: float,
        monto_intereses: float = 0,
        honorarios_pct: float = 20.0,
    ) -> dict:
        """Calcula costos estimados de litigar. Solo datos, sin recomendaciones."""
        monto_total = monto_inmediatos + monto_intereses

        honorarios = monto_total * (honorarios_pct / 100)
        tasa_justicia_pct = 3.0
        tasa_justicia = monto_total * (tasa_justicia_pct / 100)

        return {
            "monto_reclamable": round(monto_total, 2),
            "costos_estimados": {
                "honorarios": round(honorarios, 2),
                "honorarios_pct": honorarios_pct,
                "tasa_justicia": round(tasa_justicia, 2),
                "tasa_justicia_pct": tasa_justicia_pct,
            },
            "neto_si_gana": round(monto_total - honorarios, 2),
        }
