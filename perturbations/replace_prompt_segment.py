"""Perturbation: Replace a segment of the prompt template to induce drift."""

import re
import random
from typing import Optional


def replace_prompt_segment(prompt: str, segment: Optional[str] = None) -> str:
    """
    Replace a segment of the prompt to induce drift.
    If no segment specified, randomly corrupt a sentence.
    """
    if segment is None:
        sentences = re.split(r'(?<=[.!?]) +', prompt)
        if len(sentences) > 1:
            idx = random.randint(0, len(sentences) - 1)
            sentences[idx] = "[REDACTED]"
            return ' '.join(sentences)
    else:
        pattern = re.compile(re.escape(segment))
        replacement = segment[::-1]  # reverse the segment
        return pattern.sub(replacement, prompt, count=1)

    return prompt
