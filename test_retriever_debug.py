"""
Debug script: investigate why "trabajo no registrado" gives inconsistent results
across sessions in the HybridRetriever.

Run from the project root:
    cd /Users/luchoqq/repos/lexi/new/mcp
    python test_retriever_debug.py

This script tests each component of the retriever separately to isolate the
source of inconsistency.
"""

import sys
import os
import json
import re
from pathlib import Path
from collections import Counter

# Ensure src is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

# ---------------------------------------------------------------------------
# 0. Reproduce the stemming logic locally (no model loading needed)
# ---------------------------------------------------------------------------

_SUFFIXES = (
    "amientos", "imientos", "aciones", "iciones",
    "amiento", "imiento", "acion", "icion",
    "adoras", "adores", "mente",
    "adora", "ador",
    "ieron", "aron", "ando", "iendo",
    "ados", "idos", "adas", "idas",
    "iera", "iero",
    "iones", "ion",
    "encia", "ancia", "anza",
    "idad", "edad",
    "ante", "ente",
    "bles", "ble",
    "ado", "ido", "ada", "ida",
)
_MIN_STEM = 4
MIN_KEYWORD_SCORE = 0.4


def _stems(word: str) -> set:
    if len(word) <= _MIN_STEM:
        return {word}
    candidates = {word}
    for suffix in _SUFFIXES:
        if word.endswith(suffix) and len(word) - len(suffix) >= _MIN_STEM:
            candidates.add(word[: len(word) - len(suffix)])
    if word.endswith("es") and len(word) > 5:
        candidates.add(word[:-2])
    if word.endswith("s") and len(word) > _MIN_STEM:
        candidates.add(word[:-1])
    if word.endswith("a") or word.endswith("o"):
        candidates.add(word[:-1])
    return candidates


QUERY = "trabajo no registrado"

DATA_DIR = Path(__file__).parent / "src" / "ley_ar" / "data"
INDEX_PATH = DATA_DIR / "descriptores" / "descriptor_index.json"


def header(title: str) -> None:
    print()
    print("=" * 70)
    print(f"  {title}")
    print("=" * 70)


def subheader(title: str) -> None:
    print()
    print(f"--- {title} ---")


# ---------------------------------------------------------------------------
# 1. Pure keyword analysis (no model needed)
# ---------------------------------------------------------------------------

def test_keyword_matching_offline():
    """Reproduce _match_keywords logic without loading the model."""
    header("1. KEYWORD MATCHING (offline reproduction)")

    with open(INDEX_PATH, "r") as f:
        index = json.load(f)

    # Build vocab exactly as HybridRetriever.__init__ does
    vocab = {}
    for elegido, data in index.items():
        vocab[elegido] = elegido
        for sin in data.get("sinonimos", []):
            if sin not in vocab or index[elegido]["total_fallos"] > index.get(vocab[sin], {}).get("total_fallos", 0):
                vocab[sin] = elegido
    terms_sorted = sorted(vocab.keys(), key=len, reverse=True)

    text = QUERY.lower().strip()
    input_words = set(re.findall(r"\w+", text))
    input_all_stems = set()
    for w in input_words:
        input_all_stems.update(_stems(w))

    subheader("Query stems")
    for w in sorted(input_words):
        print(f"  {w!r:20s} -> {_stems(w)}")
    print(f"  ALL stems combined: {input_all_stems}")

    # --- Phase 1: exact phrase matching ---
    subheader("Phase 1: Exact phrase matches (score=1.0)")
    scores = Counter()
    exact_matches = []
    for term in terms_sorted:
        pattern = r"\b" + re.escape(term) + r"\b"
        if re.search(pattern, text):
            elegido = vocab[term]
            scores[elegido] = max(scores[elegido], 1.0)
            exact_matches.append((term, elegido))
    if exact_matches:
        for term, elegido in exact_matches:
            print(f"  term={term!r:40s} -> elegido={elegido!r}")
    else:
        print("  (none)")

    # --- Phase 2: stem-based matching ---
    subheader("Phase 2: Stem-based matching (all descriptors)")
    stem_results = []
    for elegido, data in index.items():
        all_terms = [elegido] + data.get("sinonimos", [])
        best_score = 0.0
        best_term = ""
        for term in all_terms:
            term_words = set(re.findall(r"\w+", term))
            if not term_words:
                continue
            matched_words = 0
            for tw in term_words:
                tw_stems = _stems(tw)
                if tw_stems & input_all_stems:
                    matched_words += 1
            if matched_words == 0:
                continue
            score = matched_words / len(term_words)
            if len(term_words) == 1 and matched_words == 1:
                score *= 0.3
            if score > best_score:
                best_score = score
                best_term = term
        if best_score >= MIN_KEYWORD_SCORE:
            stem_results.append((elegido, best_score, best_term))

    stem_results.sort(key=lambda x: -x[1])
    print(f"  Descriptors with stem score >= {MIN_KEYWORD_SCORE}:")
    for elegido, score, via_term in stem_results:
        marker = " *** NOISE" if score < 0.5 else ""
        print(f"    {elegido!r:45s} score={score:.2f}  via={via_term!r}{marker}")

    # --- Combined (as _match_keywords does it) ---
    subheader("Combined keyword scores (exact + stem)")
    for elegido, data in index.items():
        all_terms = [elegido] + data.get("sinonimos", [])
        best_score = 0.0
        for term in all_terms:
            term_words = set(re.findall(r"\w+", term))
            if not term_words:
                continue
            matched_words = 0
            for tw in term_words:
                tw_stems = _stems(tw)
                if tw_stems & input_all_stems:
                    matched_words += 1
            if matched_words == 0:
                continue
            score = matched_words / len(term_words)
            if len(term_words) == 1 and matched_words == 1:
                score *= 0.3
            best_score = max(best_score, score)
        if best_score >= MIN_KEYWORD_SCORE and best_score > scores.get(elegido, 0):
            scores[elegido] = best_score

    final_kw = sorted(scores.items(), key=lambda x: -x[1])
    print(f"  Final keyword results ({len(final_kw)} descriptors):")
    for desc, score in final_kw:
        print(f"    {desc!r:45s} score={score:.2f}")

    return dict(scores)


# ---------------------------------------------------------------------------
# 2. Check vocab conflicts: which elegido does each synonym resolve to?
# ---------------------------------------------------------------------------

def test_vocab_conflicts():
    """Show which descriptors share synonyms and how vocab resolution works."""
    header("2. VOCAB CONFLICT ANALYSIS")

    with open(INDEX_PATH, "r") as f:
        index = json.load(f)

    # Find all descriptors whose synonyms include terms with "trabajo" or "registr"
    relevant = {}
    for elegido, data in index.items():
        all_terms = [elegido] + data.get("sinonimos", [])
        for t in all_terms:
            if "trabajo" in t or "registr" in t:
                if elegido not in relevant:
                    relevant[elegido] = data
                break

    subheader(f"Descriptors touching 'trabajo' or 'registr' ({len(relevant)} total)")

    # Build vocab and track conflicts
    vocab = {}
    conflicts = []
    for elegido, data in index.items():
        vocab[elegido] = elegido
        for sin in data.get("sinonimos", []):
            if sin in vocab and vocab[sin] != elegido:
                old = vocab[sin]
                old_fallos = index.get(old, {}).get("total_fallos", 0)
                new_fallos = index[elegido]["total_fallos"]
                winner = elegido if new_fallos > old_fallos else old
                if "trabajo" in sin or "registr" in sin:
                    conflicts.append({
                        "synonym": sin,
                        "old_elegido": old,
                        "new_elegido": elegido,
                        "old_fallos": old_fallos,
                        "new_fallos": new_fallos,
                        "winner": winner,
                    })
            if sin not in vocab or index[elegido]["total_fallos"] > index.get(vocab[sin], {}).get("total_fallos", 0):
                vocab[sin] = elegido

    if conflicts:
        print("  Synonym conflicts (same synonym claimed by multiple descriptors):")
        for c in conflicts:
            print(f"    synonym={c['synonym']!r}")
            print(f"      {c['old_elegido']!r} (fallos={c['old_fallos']}) vs {c['new_elegido']!r} (fallos={c['new_fallos']})")
            print(f"      winner: {c['winner']!r}")
            print()
    else:
        print("  No conflicts found for relevant terms.")

    # Show final vocab mappings for key terms
    subheader("Final vocab mappings for key terms")
    key_terms = [
        "trabajo no registrado",
        "empleo no registrado",
        "trabajo en negro",
        "trabajador no registrado",
        "contrato laboral",
        "derecho del trabajo",
        "relación de trabajo",
        "relación laboral",
    ]
    for t in key_terms:
        if t in vocab:
            print(f"  vocab[{t!r:35s}] -> {vocab[t]!r}")
        else:
            print(f"  vocab[{t!r:35s}] -> NOT IN VOCAB")


# ---------------------------------------------------------------------------
# 3. Full retriever test (requires model + FAISS)
# ---------------------------------------------------------------------------

def test_full_retriever():
    """Load the actual HybridRetriever and run all three methods."""
    header("3. FULL HYBRID RETRIEVER TEST (model + FAISS)")
    print("  Loading model and FAISS index (this may take a moment)...")

    from ley_ar.services.hybrid_retriever import HybridRetriever

    retriever = HybridRetriever()

    # --- _match_keywords ---
    subheader("_match_keywords results")
    kw_scores = retriever._match_keywords(QUERY)
    kw_sorted = sorted(kw_scores.items(), key=lambda x: -x[1])
    for desc, score in kw_sorted:
        print(f"  {desc!r:45s} score={score:.4f}")

    # --- _match_semantic ---
    subheader("_match_semantic results")
    sem_scores = retriever._match_semantic(QUERY, top_k=15)
    sem_sorted = sorted(sem_scores.items(), key=lambda x: -x[1])
    for desc, score in sem_sorted:
        print(f"  {desc!r:45s} score={score:.4f}")

    # --- match_descriptors (combined) ---
    subheader("match_descriptors results (combined)")
    combined = retriever.match_descriptors(QUERY)
    for desc, score in combined:
        source = []
        if desc in kw_scores:
            source.append(f"kw={kw_scores[desc]:.2f}")
        if desc in sem_scores:
            source.append(f"sem={sem_scores[desc]:.2f}")
        print(f"  {desc!r:45s} score={score:.4f}  [{', '.join(source)}]")

    # --- full search ---
    subheader("Full search() results")
    result = retriever.search(QUERY)
    print(f"  Descriptors used ({len(result['descriptors_matched'])}):")
    for d in result["descriptors_matched"]:
        print(f"    {d['descriptor']!r:45s} score={d['score']:.2f}")
    print(f"  Articles returned: {len(result['articles'])}")
    for art in result["articles"][:5]:
        print(f"    {art['id']:20s} weighted_score={art['weighted_score']:.2f}  signals={art['signals']}")

    # --- Run it 3 times to check consistency ---
    subheader("Consistency check: running match_descriptors 3 times")
    results = []
    for i in range(3):
        r = retriever.match_descriptors(QUERY)
        results.append(r)
        top3 = [(d, round(s, 4)) for d, s in r[:3]]
        print(f"  Run {i+1}: top 3 = {top3}")

    # Check if all runs are identical
    all_same = all(
        [(d, round(s, 4)) for d, s in r] == [(d, round(s, 4)) for d, s in results[0]]
        for r in results[1:]
    )
    if all_same:
        print("  -> All 3 runs produced IDENTICAL results within this session.")
    else:
        print("  -> WARNING: Results DIFFER between runs within the same session!")

    return kw_scores, sem_scores


# ---------------------------------------------------------------------------
# 4. Root cause analysis
# ---------------------------------------------------------------------------

def print_root_cause_analysis():
    header("4. ROOT CAUSE ANALYSIS")

    analysis = """
FINDING 1: Keyword matching is DETERMINISTIC and CORRECT
---------------------------------------------------------
The query "trabajo no registrado" ALWAYS gets score=1.0 via exact phrase match
because "trabajo no registrado" is literally a key in descriptor_index.json
AND a synonym of itself. The regex \\b-match on the full phrase guarantees this.

FINDING 2: Stem matching introduces NOISE but is also deterministic
--------------------------------------------------------------------
The stem-based phase (phase 2 of _match_keywords) picks up extra descriptors:
- "trabajador no registrado" -> 3/3 words match via stems (score=1.0)
  (stems of "trabajador" include "trabaj", which overlaps with "trabajo")
- "trabajo voluntario" -> 1/2 words match (score=0.50) -- NOISE
- "empleo no registrado" -> 2/3 words match (score=0.67)
- "trabajo parcialmente registrado" -> matches via stems too

These are deterministic. The keyword matcher alone cannot explain inconsistency.

FINDING 3: The SEMANTIC matcher is the likely source of inconsistency
----------------------------------------------------------------------
The semantic matcher uses SentenceTransformer + FAISS. Possible causes:
  a) Model non-determinism: some transformer models use dropout at inference
     or have floating-point non-determinism across runs. The model
     "dariolopez/bge-m3-es-legal-tmp-6" may behave differently depending on:
     - CUDA vs CPU execution
     - Different model weights loaded (cache issues)
     - Torch random seed state
  b) FAISS index: inner-product search is deterministic given the same query
     vector. But if the query vector changes (due to model non-determinism),
     the results change.

FINDING 4: Combined scoring uses max(kw, sem) -- semantic can DOMINATE
-----------------------------------------------------------------------
match_descriptors() takes max(keyword_score, semantic_score) per descriptor.
If semantic gives "relacion de trabajo" score=1.0 in one session but 0.6 in
another, that descriptor's final score swings wildly. Meanwhile, keyword
matching gives it only 0.33 (below threshold), so keyword can't compensate.

FINDING 5: Synonym vocab conflicts cause surprising mappings
-------------------------------------------------------------
Multiple descriptors share the same synonyms (e.g., "contrato laboral" and
"derecho del trabajo" appear as synonyms of MANY descriptors). The vocab dict
resolves conflicts by total_fallos count, meaning a synonym like "contrato
laboral" might map to "relacion de trabajo" (51 fallos) instead of "trabajo
no registrado" (14 fallos). This is deterministic but may cause unexpected
exact-phrase matches if the user's query happens to contain a shared synonym.

RECOMMENDATIONS:
1. Add torch.manual_seed() / np.random.seed() before encoding to test if
   model non-determinism is the cause.
2. Check if the model is being loaded from cache vs re-downloaded between
   sessions (different model versions = different embeddings).
3. Consider giving keyword exact-match a BONUS over semantic scores, e.g.,
   final_score = max(kw * 1.2, sem) so that a perfect keyword match always
   wins over a mediocre semantic match.
4. The stem matcher scoring "trabajo voluntario" at 0.50 is noise -- consider
   requiring at least 2 word matches for multi-word descriptors, or raising
   MIN_KEYWORD_SCORE to 0.5.
"""
    print(analysis)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Phase 1 & 2: no model needed, fast
    kw_offline = test_keyword_matching_offline()
    test_vocab_conflicts()

    # Phase 3: requires model loading (slow, ~30s first time)
    try:
        kw_live, sem_live = test_full_retriever()
    except Exception as e:
        print(f"\n  ERROR loading full retriever: {e}")
        print("  Skipping full retriever test. The offline analysis above is still valid.")
        print("  Make sure you have the dependencies: pip install sentence-transformers faiss-cpu")

    # Phase 4: analysis
    print_root_cause_analysis()
