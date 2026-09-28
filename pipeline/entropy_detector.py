"""
Signal 3: Structural Entropy, Compression & N-Gram Repetition Detector.
Measures algorithmic information density via zlib compression ratio,
n-gram repetition rates, and synthetic boilerplate lexicon density.
"""

import zlib
import re
from collections import Counter
from typing import Dict, Any, List

# Curated catalog of distinctive synthetic phrasing and transitions
AI_SYNTHETIC_LEXICON = [
    "delve", "delving", "delves",
    "tapestry", "rich tapestry", "vibrant tapestry",
    "testament", "stands as a testament", "serves as a testament",
    "beacon", "beacon of hope", "beacon of",
    "multifaceted", "pivotal", "pivotal role",
    "crucial role", "vital role", "plays a crucial role",
    "in conclusion", "in summary", "to summarize",
    "furthermore", "moreover", "it is worth noting",
    "it is important to note", "it should be noted",
    "fosters", "fostering", "underscores", "underscoring",
    "navigating", "navigating the complexities", "dynamic landscape",
    "ever-evolving", "at the intersection of", "unwavering",
    "testament to the", "a reminder of the", "harnessing the power"
]

class EntropyDetector:
    def __init__(self):
        self.ai_lexicon = [item.lower() for item in AI_SYNTHETIC_LEXICON]

    def _extract_ngrams(self, tokens: List[str], n: int) -> List[tuple]:
        return [tuple(tokens[i:i+n]) for i in range(len(tokens) - n + 1)]

    def analyze(self, text: str) -> Dict[str, Any]:
        """
        Analyze compressibility, n-gram redundancy, and synthetic boilerplate density.
        """
        raw_bytes = text.strip().encode("utf-8")
        if len(raw_bytes) < 30:
            return {
                "score": 0.50,
                "confidence": 0.40,
                "metrics": {
                    "compression_ratio": 1.0,
                    "boilerplate_count": 0,
                    "note": "Input text too brief for entropy profiling"
                },
                "reasoning": "Sample size too small for statistical compression analysis."
            }

        # 1. Zlib Compression Ratio (Approximation of Kolmogorov complexity)
        compressed = zlib.compress(raw_bytes)
        compression_ratio = len(compressed) / len(raw_bytes)

        # 2. Tokenize for N-gram and boilerplate analysis
        tokens = re.findall(r'\b[a-zA-Z0-9_\'-]+\b', text.lower())
        total_tokens = len(tokens)

        # 3-gram and 4-gram repetition
        trigrams = self._extract_ngrams(tokens, 3)
        tri_counts = Counter(trigrams)
        repeated_trigrams = sum(count - 1 for count in tri_counts.values() if count > 1)
        trigram_repetition_rate = repeated_trigrams / max(1, len(trigrams))

        # 3. AI Boilerplate Density
        lower_text = text.lower()
        matched_markers = []
        for phrase in self.ai_lexicon:
            # Match whole words or phrases
            pattern = r'\b' + re.escape(phrase) + r'\b'
            matches = re.findall(pattern, lower_text)
            if matches:
                matched_markers.extend(matches)

        boilerplate_density = len(matched_markers) / (max(1, total_tokens) / 100.0)

        # 4. Score Calculation
        score = 0.45

        # Compression contribution: Highly compressible text (low ratio) in prose often indicates repetitive or formulaic text
        # For standard English text of 100-500 words, normal compression ratio is ~0.60 - 0.78
        if compression_ratio < 0.58 and total_tokens > 60:
            score += 0.15
        elif compression_ratio > 0.75:
            score -= 0.15

        # Boilerplate density contribution
        if len(matched_markers) >= 4 or boilerplate_density >= 2.0:
            score += 0.35
        elif len(matched_markers) >= 2 or boilerplate_density >= 1.0:
            score += 0.20
        elif len(matched_markers) == 1:
            score += 0.08
        else:
            score -= 0.10

        # N-gram repetition contribution
        if trigram_repetition_rate > 0.08:
            score += 0.12

        final_score = max(0.05, min(0.95, score))
        confidence = min(0.95, 0.60 + min(0.35, len(matched_markers) * 0.08 + (total_tokens / 500.0) * 0.1))

        reasoning = (
            f"Compression ratio={compression_ratio:.3f}, Boilerplate markers={len(matched_markers)} "
            f"({', '.join(set(matched_markers)) if matched_markers else 'none'}), "
            f"Trigram repetition rate={trigram_repetition_rate:.3f}."
        )

        return {
            "score": round(final_score, 4),
            "confidence": round(confidence, 4),
            "metrics": {
                "compression_ratio": round(compression_ratio, 4),
                "raw_byte_length": len(raw_bytes),
                "compressed_byte_length": len(compressed),
                "boilerplate_count": len(matched_markers),
                "boilerplate_density_per_100w": round(boilerplate_density, 3),
                "trigram_repetition_rate": round(trigram_repetition_rate, 4),
                "detected_markers": list(set(matched_markers))
            },
            "reasoning": reasoning
        }
