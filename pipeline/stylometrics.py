"""
Signal 2: Pure Python Stylometric Heuristics.
Evaluates lexical diversity, sentence length variance (burstiness), hapax legomena,
and punctuation cadence without external NLP dependencies.
"""

import math
import re
from collections import Counter
from typing import Dict, Any, List

class StylometricDetector:
    def __init__(self):
        pass

    def _tokenize(self, text: str) -> List[str]:
        """Extract lowercase alphanumeric tokens."""
        return re.findall(r'\b[a-zA-Z0-9_\'-]+\b', text.lower())

    def _get_sentences(self, text: str) -> List[str]:
        """Split text into sentences based on punctuation."""
        raw_sentences = re.split(r'[.!?]+(?:\s+|$)', text)
        return [s.strip() for s in raw_sentences if len(self._tokenize(s)) >= 2]

    def analyze(self, text: str) -> Dict[str, Any]:
        """
        Analyze stylometric features of text and return normalized AI probability score (0.0 to 1.0).
        """
        tokens = self._tokenize(text)
        sentences = self._get_sentences(text)

        total_tokens = len(tokens)
        if total_tokens < 10:
            return {
                "score": 0.50,
                "confidence": 0.40,
                "metrics": {
                    "token_count": total_tokens,
                    "sentence_count": len(sentences),
                    "note": "Text too short for robust stylometric profiling"
                },
                "reasoning": "Insufficient word count for reliable stylometric distribution."
            }

        # 1. Lexical Richness Metrics
        unique_tokens = len(set(tokens))
        ttr = unique_tokens / total_tokens
        root_ttr = unique_tokens / math.sqrt(total_tokens)

        # 2. Hapax Legomena (words appearing exactly once)
        counts = Counter(tokens)
        hapax_count = sum(1 for count in counts.values() if count == 1)
        hapax_ratio = hapax_count / unique_tokens if unique_tokens > 0 else 0.0

        # 3. Sentence Length Variance & Burstiness
        sentence_lengths = [len(self._tokenize(s)) for s in sentences]
        if len(sentence_lengths) >= 2:
            mean_len = sum(sentence_lengths) / len(sentence_lengths)
            variance = sum((l - mean_len) ** 2 for l in sentence_lengths) / len(sentence_lengths)
            std_dev = math.sqrt(variance)
            # Coefficient of Variation (CV) as Burstiness proxy
            cv = std_dev / mean_len if mean_len > 0 else 0.0
        else:
            mean_len = total_tokens
            variance = 0.0
            std_dev = 0.0
            cv = 0.25  # Neutral fallback

        # 4. Punctuation Profile
        punct_marks = re.findall(r'[,;:—\-\(\)]', text)
        punct_density = len(punct_marks) / total_tokens if total_tokens > 0 else 0.0

        # 5. Composite Stylometric Synthetic Probability Calculation
        # Lower CV (low burstiness / uniform sentences) -> higher AI probability
        # Lower Hapax ratio (less idiosyncratic vocabulary) -> higher AI probability
        # Normal human CV is typically > 0.40; AI typically clusters around 0.15 - 0.35

        score = 0.50  # Start neutral

        # Burstiness contribution
        if cv < 0.22:
            score += 0.22  # Unusually uniform sentence rhythm
        elif cv < 0.32:
            score += 0.10
        elif cv > 0.50:
            score -= 0.20  # Highly bursty human rhythm
        elif cv > 0.40:
            score -= 0.10

        # Hapax legomena contribution (Human text usually has hapax_ratio > 0.60)
        if hapax_ratio < 0.45:
            score += 0.18  # Low vocabulary diversity
        elif hapax_ratio < 0.55:
            score += 0.08
        elif hapax_ratio > 0.72:
            score -= 0.20  # High creative lexical variety
        elif hapax_ratio > 0.62:
            score -= 0.10

        # Root TTR contribution
        if root_ttr < 4.5 and total_tokens > 50:
            score += 0.10
        elif root_ttr > 7.5:
            score -= 0.12

        # Punctuation cadence contribution
        # LLMs maintain very regular comma punctuation; humans often use dashes or varied punctuation
        if 0.04 <= punct_density <= 0.08 and len(punct_marks) > 4:
            score += 0.05
        elif punct_density > 0.12 or ('—' in text or '--' in text):
            score -= 0.06

        # Bound score between 0.05 and 0.95
        final_score = max(0.05, min(0.95, score))

        # Confidence is higher for longer texts with more sentences
        confidence = min(0.95, 0.55 + (min(total_tokens, 300) / 1000.0) + (min(len(sentences), 10) * 0.02))

        reasoning = (
            f"Stylometric profile: CV (burstiness)={cv:.2f}, Hapax ratio={hapax_ratio:.2f}, "
            f"Root TTR={root_ttr:.2f}, Mean sentence length={mean_len:.1f} words."
        )

        return {
            "score": round(final_score, 4),
            "confidence": round(confidence, 4),
            "metrics": {
                "token_count": total_tokens,
                "sentence_count": len(sentences),
                "type_token_ratio": round(ttr, 4),
                "root_ttr": round(root_ttr, 4),
                "hapax_legomena_ratio": round(hapax_ratio, 4),
                "burstiness_cv": round(cv, 4),
                "sentence_std_dev": round(std_dev, 2),
                "mean_sentence_length": round(mean_len, 2),
                "punctuation_density": round(punct_density, 4)
            },
            "reasoning": reasoning
        }
