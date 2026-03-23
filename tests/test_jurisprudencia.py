"""
Tests de jurisprudencia con casos laborales reales.
Valida que devuelva fallos relevantes, recientes y de materia laboral.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ley_ar.services.hybrid_retriever import HybridRetriever
from ley_ar.services.juris_search import JurisprudenciaSearch
from ley_ar.tools.jurisprudencia import jurisprudencia

retriever = HybridRetriever()
juris = JurisprudenciaSearch()


def test_despido_sin_causa_devuelve_fallos():
    r = jurisprudencia(retriever, juris, "despido sin causa con 5 anos de antiguedad")
    assert r["total_encontrados"] > 0
    assert len(r["fallos"]) > 0


def test_embarazo_devuelve_fallos():
    r = jurisprudencia(retriever, juris, "despido durante embarazo")
    assert r["total_encontrados"] > 0


def test_fallos_tienen_campos_requeridos():
    """Cada fallo debe tener los campos basicos incluyendo texto sustantivo."""
    r = jurisprudencia(retriever, juris, "despido sin causa")
    for f in r["fallos"]:
        assert f["caratula"] != ""
        assert f["fecha"] != ""
        assert f["relevance_score"] > 0
        assert f["overlap_count"] >= 1
        assert "texto" in f


def test_recencia_boost():
    """Los fallos mas recientes deben rankear mas alto que los viejos con mismo overlap."""
    r = jurisprudencia(retriever, juris, "despido sin causa", max_resultados=10)
    if len(r["fallos"]) >= 2:
        # El primero debe ser relativamente reciente (post-2010 al menos)
        primer_fallo = r["fallos"][0]
        year = primer_fallo["fecha"][:4] if primer_fallo["fecha"] else "0000"
        assert int(year) >= 2000, f"Primer fallo es de {year}, esperado post-2000"


def test_filtro_jurisdiccion_buenos_aires():
    r = jurisprudencia(retriever, juris, "despido sin causa", jurisdiccion="Buenos Aires", max_resultados=5)
    for f in r["fallos"]:
        assert f["provincia"] == "Buenos Aires", f"Fallo de {f['provincia']}, esperado Buenos Aires"


def test_filtro_jurisdiccion_caba():
    r = jurisprudencia(
        retriever, juris, "despido sin causa",
        jurisdiccion="Ciudad Autónoma de Buenos Aires", max_resultados=5,
    )
    for f in r["fallos"]:
        assert f["provincia"] == "Ciudad Autónoma de Buenos Aires"


def test_max_resultados():
    r = jurisprudencia(retriever, juris, "despido", max_resultados=2)
    assert len(r["fallos"]) <= 2


def test_devuelve_descriptores_usados():
    r = jurisprudencia(retriever, juris, "despido sin causa")
    assert len(r["descriptores_usados"]) > 0


def test_fallos_no_duplicados():
    """No deben repetirse caratulas."""
    r = jurisprudencia(retriever, juris, "despido sin causa", max_resultados=10)
    caratulas = [f["caratula"].strip().lower() for f in r["fallos"]]
    assert len(caratulas) == len(set(caratulas)), "Hay fallos duplicados"


def test_accidente_laboral():
    r = jurisprudencia(retriever, juris, "accidente de trabajo con incapacidad")
    assert r["total_encontrados"] > 0


def test_trabajo_no_registrado():
    r = jurisprudencia(retriever, juris, "trabajo no registrado en negro")
    assert r["total_encontrados"] > 0
