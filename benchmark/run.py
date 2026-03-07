"""
Benchmark de calidad de retrieval.

Corre los casos definidos en cases.py contra buscar_articulos y jurisprudencia,
y reporta métricas de precisión.

Uso:
    python benchmark/run.py              # Reporte completo
    python benchmark/run.py --verbose    # Detalle de cada caso
    python benchmark/run.py --json       # Output JSON para comparación automática
"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cases import ARTICULOS_CASES, JURISPRUDENCIA_CASES
from ley_ar.services.hybrid_retriever import HybridRetriever
from ley_ar.services.legislation_store import LegislationStore
from ley_ar.services.juris_search import JurisprudenciaSearch
from ley_ar.tools.buscar_articulos import buscar_articulos
from ley_ar.tools.jurisprudencia import jurisprudencia


def eval_articulos(retriever, store, cases, verbose=False):
    results = []

    for case in cases:
        t0 = time.time()
        result = buscar_articulos(retriever, store, case["query"], max_resultados=case["top_k"])
        elapsed = time.time() - t0

        found_ids = [a["codigo"] + "_" + a["articulo"] for a in result["articulos"]]
        descriptors = [d["descriptor"] for d in result["descriptores_usados"]]

        # expected_articles: todos deben estar presentes
        expected_hits = 0
        expected_misses = []
        for exp in case["expected_articles"]:
            if exp in found_ids:
                expected_hits += 1
            else:
                expected_misses.append(exp)

        # expected_any_of: al menos uno debe estar
        any_of_hit = False
        if not case.get("expected_any_of"):
            any_of_hit = True  # no requirement
        else:
            for exp in case["expected_any_of"]:
                if exp in found_ids:
                    any_of_hit = True
                    break

        total_expected = len(case["expected_articles"])
        recall = expected_hits / total_expected if total_expected > 0 else 1.0
        passed = len(expected_misses) == 0 and any_of_hit

        entry = {
            "id": case["id"],
            "passed": passed,
            "recall": recall,
            "any_of_hit": any_of_hit,
            "expected_misses": expected_misses,
            "found_ids": found_ids,
            "descriptors_matched": len(descriptors),
            "time_ms": round(elapsed * 1000),
        }
        results.append(entry)

        if verbose:
            status = "PASS" if passed else "FAIL"
            print(f"  [{status}] {case['id']}")
            print(f"    query: {case['query']}")
            print(f"    found: {found_ids}")
            print(f"    descriptors: {descriptors[:5]}{'...' if len(descriptors) > 5 else ''}")
            if expected_misses:
                print(f"    MISSING: {expected_misses}")
            if not any_of_hit:
                print(f"    MISSING any_of: {case['expected_any_of']}")
            print(f"    time: {entry['time_ms']}ms")
            print()

    return results


def eval_jurisprudencia(retriever, juris_search, cases, verbose=False):
    results = []

    for case in cases:
        t0 = time.time()
        result = jurisprudencia(retriever, juris_search, case["query"], max_resultados=case["max_resultados"])
        elapsed = time.time() - t0

        fallos = result["fallos"]
        n_found = len(fallos)
        min_ok = n_found >= case["min_results"]

        # Check descriptor overlap if specified
        overlap_ok = True
        overlap_found = []
        if case.get("expected_descriptor_overlap"):
            all_fallo_descs = set()
            for f in fallos:
                for d in f.get("descriptors_overlap", []):
                    all_fallo_descs.add(d.lower())

            for exp_desc in case["expected_descriptor_overlap"]:
                if exp_desc.lower() in all_fallo_descs:
                    overlap_found.append(exp_desc)

            # At least half of expected descriptors should appear
            overlap_ok = len(overlap_found) >= len(case["expected_descriptor_overlap"]) / 2

        passed = min_ok and overlap_ok

        # Recency: average year of returned fallos
        years = []
        for f in fallos:
            if f.get("fecha") and len(f["fecha"]) >= 4:
                try:
                    years.append(int(f["fecha"][:4]))
                except ValueError:
                    pass
        avg_year = round(sum(years) / len(years)) if years else 0

        entry = {
            "id": case["id"],
            "passed": passed,
            "n_found": n_found,
            "min_required": case["min_results"],
            "min_ok": min_ok,
            "overlap_ok": overlap_ok,
            "overlap_found": overlap_found,
            "avg_year": avg_year,
            "time_ms": round(elapsed * 1000),
        }
        results.append(entry)

        if verbose:
            status = "PASS" if passed else "FAIL"
            print(f"  [{status}] {case['id']}")
            print(f"    query: {case['query']}")
            print(f"    found: {n_found} fallos (min: {case['min_results']})")
            for f in fallos[:3]:
                print(f"      - {f.get('caratula', '?')[:60]} ({f.get('fecha', '?')[:4]})")
            if avg_year:
                print(f"    avg year: {avg_year}")
            if not overlap_ok:
                print(f"    MISSING descriptors: {[d for d in case.get('expected_descriptor_overlap', []) if d not in overlap_found]}")
            print(f"    time: {entry['time_ms']}ms")
            print()

    return results


def print_summary(art_results, juris_results):
    art_passed = sum(1 for r in art_results if r["passed"])
    juris_passed = sum(1 for r in juris_results if r["passed"])
    art_total = len(art_results)
    juris_total = len(juris_results)

    total_passed = art_passed + juris_passed
    total = art_total + juris_total

    print("=" * 60)
    print(f"BENCHMARK RESULTS")
    print("=" * 60)
    print(f"  Articulos:      {art_passed}/{art_total}")
    print(f"  Jurisprudencia: {juris_passed}/{juris_total}")
    print(f"  TOTAL:          {total_passed}/{total} ({round(total_passed/total*100)}%)")
    print()

    # Recall promedio para artículos
    recalls = [r["recall"] for r in art_results]
    avg_recall = sum(recalls) / len(recalls) if recalls else 0
    print(f"  Avg recall (articulos): {avg_recall:.0%}")

    # Año promedio jurisprudencia
    years = [r["avg_year"] for r in juris_results if r["avg_year"]]
    avg_year = round(sum(years) / len(years)) if years else 0
    print(f"  Avg year (jurisprudencia): {avg_year}")

    # Tiempo promedio
    all_times = [r["time_ms"] for r in art_results + juris_results]
    avg_time = round(sum(all_times) / len(all_times)) if all_times else 0
    print(f"  Avg time per query: {avg_time}ms")
    print()

    # Failures
    failures = [r for r in art_results + juris_results if not r["passed"]]
    if failures:
        print("FAILURES:")
        for f in failures:
            print(f"  - {f['id']}: {f.get('expected_misses', '')} {'' if f.get('min_ok', True) else 'insufficient results'}")
    print()


def main():
    verbose = "--verbose" in sys.argv
    as_json = "--json" in sys.argv

    print("Loading services...")
    retriever = HybridRetriever()
    store = LegislationStore()
    juris_search = JurisprudenciaSearch()
    print("Ready.\n")

    if verbose or not as_json:
        print("--- ARTICULOS ---")
    art_results = eval_articulos(retriever, store, ARTICULOS_CASES, verbose=verbose)

    if verbose or not as_json:
        print("--- JURISPRUDENCIA ---")
    juris_results = eval_jurisprudencia(retriever, juris_search, JURISPRUDENCIA_CASES, verbose=verbose)

    if as_json:
        output = {
            "articulos": art_results,
            "jurisprudencia": juris_results,
            "summary": {
                "articulos_passed": sum(1 for r in art_results if r["passed"]),
                "articulos_total": len(art_results),
                "juris_passed": sum(1 for r in juris_results if r["passed"]),
                "juris_total": len(juris_results),
            },
        }
        print(json.dumps(output, indent=2, ensure_ascii=False))
    else:
        print_summary(art_results, juris_results)


if __name__ == "__main__":
    main()
