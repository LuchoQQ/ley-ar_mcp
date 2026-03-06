"""
HybridRetriever: combina keyword matching con busqueda semantica (FAISS)
para obtener lo mejor de ambos metodos.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Dict, List, Set, Tuple

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

MODEL_NAME = "dariolopez/bge-m3-es-legal-tmp-6"
DATA_DIR = Path(__file__).parent.parent / "data"
FAISS_PATH = DATA_DIR / "embeddings" / "descriptor_embeddings.faiss"
MAPPINGS_PATH = DATA_DIR / "embeddings" / "descriptor_mappings.json"
INDEX_PATH = DATA_DIR / "descriptores" / "descriptor_index.json"

MIN_SEMANTIC_SIMILARITY = 0.55
MIN_KEYWORD_SCORE = 0.4

# --- Stemming en espanol ---

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


def _stems(word: str) -> Set[str]:
    if len(word) <= _MIN_STEM:
        return {word}
    candidates = {word}
    for suffix in _SUFFIXES:
        if word.endswith(suffix) and len(word) - len(suffix) >= _MIN_STEM:
            candidates.add(word[:len(word) - len(suffix)])
    if word.endswith("es") and len(word) > 5:
        candidates.add(word[:-2])
    if word.endswith("s") and len(word) > _MIN_STEM:
        candidates.add(word[:-1])
    if word.endswith("a") or word.endswith("o"):
        candidates.add(word[:-1])
    return candidates


class HybridRetriever:

    def __init__(self):
        with open(INDEX_PATH, "r") as f:
            self.index = json.load(f)

        # Keyword: vocabulario de sinonimos
        self.vocab = {}
        for elegido, data in self.index.items():
            self.vocab[elegido] = elegido
            for sin in data.get("sinonimos", []):
                if sin not in self.vocab or self.index[elegido]["total_fallos"] > self.index.get(self.vocab[sin], {}).get("total_fallos", 0):
                    self.vocab[sin] = elegido
        self.terms_sorted = sorted(self.vocab.keys(), key=len, reverse=True)

        # Semantico: modelo + FAISS
        self.model = SentenceTransformer(MODEL_NAME)
        self.faiss_index = faiss.read_index(str(FAISS_PATH))
        with open(MAPPINGS_PATH, "r") as f:
            self.mappings = json.load(f)

    def _match_keywords(self, user_input: str) -> Dict[str, float]:
        text = user_input.lower().strip()
        input_words = set(re.findall(r'\w+', text))
        input_all_stems = set()
        for w in input_words:
            input_all_stems.update(_stems(w))

        scores: Counter = Counter()

        for term in self.terms_sorted:
            pattern = r'\b' + re.escape(term) + r'\b'
            if re.search(pattern, text):
                elegido = self.vocab[term]
                scores[elegido] = max(scores[elegido], 1.0)

        for elegido, data in self.index.items():
            all_terms = [elegido] + data.get("sinonimos", [])
            best_score = 0.0
            for term in all_terms:
                term_words = set(re.findall(r'\w+', term))
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

        return dict(scores)

    def _match_semantic(self, user_input: str, top_k: int = 15) -> Dict[str, float]:
        query_embedding = self.model.encode(
            [user_input.lower().strip()],
            normalize_embeddings=True,
        )
        query_embedding = np.array(query_embedding, dtype=np.float32)
        scores_arr, indices = self.faiss_index.search(query_embedding, top_k)

        descriptor_scores: Dict[str, float] = {}
        for score, idx in zip(scores_arr[0], indices[0]):
            if idx == -1 or score < MIN_SEMANTIC_SIMILARITY:
                continue
            elegido = self.mappings[idx]["elegido"]
            descriptor_scores[elegido] = max(descriptor_scores.get(elegido, 0), float(score))

        return descriptor_scores

    def match_descriptors(self, user_input: str) -> List[Tuple[str, float]]:
        kw_scores = self._match_keywords(user_input)
        sem_scores = self._match_semantic(user_input)

        all_descriptors = set(kw_scores.keys()) | set(sem_scores.keys())
        combined = {}
        for desc in all_descriptors:
            combined[desc] = max(kw_scores.get(desc, 0), sem_scores.get(desc, 0))

        return sorted(combined.items(), key=lambda x: -x[1])

    def _hierarchy_similarity(self, anchor_path: str, other_path: str) -> float:
        if not anchor_path or not other_path:
            return 0.5
        parts_a = [p.strip().lower() for p in anchor_path.split("/")]
        parts_b = [p.strip().lower() for p in other_path.split("/")]
        shared = 0
        for a, b in zip(parts_a, parts_b):
            if a == b:
                shared += 1
            else:
                break
        if shared == 0:
            return 0.0
        base_sim = shared / len(parts_a)
        extra_depth = len(parts_b) - shared
        if extra_depth > 0:
            base_sim *= 0.5 ** extra_depth
        return base_sim

    def _get_branch(self, desc: str) -> str:
        path = self.index.get(desc, {}).get("preferido", "")
        if not path:
            return desc
        parts = [p.strip().lower() for p in path.split("/")]
        return "/".join(parts[:min(3, len(parts))])

    def _apply_hierarchy_weighting(self, matched: List[Tuple[str, float]]) -> List[Tuple[str, float]]:
        if len(matched) <= 1:
            return matched

        branches: Dict[str, List[Tuple[str, float]]] = {}
        for desc, score in matched:
            branch = self._get_branch(desc)
            if branch not in branches:
                branches[branch] = []
            branches[branch].append((desc, score))

        weighted = []
        for branch, descs in branches.items():
            descs.sort(key=lambda x: -x[1])
            anchor_name = descs[0][0]
            anchor_path = self.index.get(anchor_name, {}).get("preferido", "")
            weighted.append((anchor_name, descs[0][1]))
            for desc, score in descs[1:]:
                desc_path = self.index.get(desc, {}).get("preferido", "")
                hier_sim = self._hierarchy_similarity(anchor_path, desc_path)
                weighted.append((desc, score * hier_sim))

        weighted.sort(key=lambda x: -x[1])
        return weighted

    def get_articles(self, descriptor_scores: List[Tuple[str, float]], min_signals: int = 1, top_k: int = 10) -> List[Dict]:
        article_scores = {}
        for desc, desc_score in descriptor_scores:
            data = self.index.get(desc)
            if not data:
                continue
            for art in data["articulos"]:
                art_id = art["id"]
                if art_id not in article_scores:
                    article_scores[art_id] = {
                        "id": art_id, "signals": 0,
                        "weighted_score": 0.0, "total_citas": 0,
                        "from_descriptors": [],
                    }
                article_scores[art_id]["signals"] += 1
                article_scores[art_id]["total_citas"] += art["citas"]
                article_scores[art_id]["weighted_score"] += art["citas"] * desc_score
                article_scores[art_id]["from_descriptors"].append(
                    {"descriptor": desc, "citas": art["citas"], "score": round(desc_score, 2)}
                )
        filtered = [a for a in article_scores.values() if a["signals"] >= min_signals]
        for a in filtered:
            a["weighted_score"] = round(a["weighted_score"], 2)
        filtered.sort(key=lambda x: x["weighted_score"], reverse=True)
        return filtered[:top_k]

    def search(self, user_input: str, top_k: int = 10, min_signals: int = 1, max_descriptors: int = 8) -> Dict:
        all_matched = self.match_descriptors(user_input)

        high_confidence = [(d, s) for d, s in all_matched if s >= 0.6]
        if len(high_confidence) >= 2:
            selected = high_confidence[:max_descriptors]
        else:
            selected = all_matched[:max_descriptors]

        weighted = self._apply_hierarchy_weighting(selected)
        weighted = [(d, s) for d, s in weighted if s >= 0.2]

        effective_min = min(min_signals, len(weighted)) if weighted else 1

        articles = self.get_articles(weighted, min_signals=effective_min, top_k=top_k)

        return {
            "input": user_input,
            "descriptors_matched": [
                {"descriptor": d, "score": round(s, 2)} for d, s in weighted
            ],
            "articles": articles,
        }
