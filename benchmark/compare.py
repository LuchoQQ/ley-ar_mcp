"""
Compara dos snapshots de benchmark (JSON) para detectar regresiones.

Uso:
    python benchmark/run.py --json > benchmark/snapshots/baseline.json
    # ... hacer cambios en services/ ...
    python benchmark/run.py --json > benchmark/snapshots/after.json
    python benchmark/compare.py benchmark/snapshots/baseline.json benchmark/snapshots/after.json
"""

import json
import sys


def compare(before_path: str, after_path: str):
    with open(before_path) as f:
        before = json.load(f)
    with open(after_path) as f:
        after = json.load(f)

    print(f"Comparing: {before_path} → {after_path}\n")

    # Summary
    bs = before["summary"]
    af = after["summary"]

    def delta(label, b, a, total_key):
        bt = b[total_key]
        at = a[total_key]
        bp = b[label]
        ap = a[label]
        diff = ap - bp
        sign = "+" if diff > 0 else ""
        status = "BETTER" if diff > 0 else ("WORSE" if diff < 0 else "SAME")
        print(f"  {label}: {bp}/{bt} → {ap}/{at} ({sign}{diff}) [{status}]")

    delta("articulos_passed", bs, af, "articulos_total")
    delta("juris_passed", bs, af, "juris_total")
    print()

    # Per-case regressions
    before_cases = {r["id"]: r for r in before.get("articulos", []) + before.get("jurisprudencia", [])}
    after_cases = {r["id"]: r for r in after.get("articulos", []) + after.get("jurisprudencia", [])}

    regressions = []
    improvements = []

    for case_id in before_cases:
        if case_id not in after_cases:
            continue
        b = before_cases[case_id]
        a = after_cases[case_id]

        if b["passed"] and not a["passed"]:
            regressions.append(case_id)
        elif not b["passed"] and a["passed"]:
            improvements.append(case_id)

    if improvements:
        print("IMPROVEMENTS:")
        for c in improvements:
            print(f"  + {c}")
    if regressions:
        print("REGRESSIONS:")
        for c in regressions:
            print(f"  - {c}")
    if not improvements and not regressions:
        print("No changes in pass/fail status.")
    print()


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python benchmark/compare.py <before.json> <after.json>")
        sys.exit(1)
    compare(sys.argv[1], sys.argv[2])
