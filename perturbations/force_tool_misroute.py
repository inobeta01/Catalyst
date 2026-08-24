"""Perturbation: Force the agent to select the wrong tool."""

import random
from typing import Dict, List
from collections import OrderedDict


def force_tool_misroute(tools: Dict[str, callable], preferred: str) -> List[str]:
    """
    Given a dict of tool_name -> function, return all tool names
    except the preferred one, encouraging misrouting.
    """
    available = list(tools.keys())
    if preferred in available:
        available.remove(preferred)
    random.shuffle(available)
    return available[:max(1, len(available) - 1)]
