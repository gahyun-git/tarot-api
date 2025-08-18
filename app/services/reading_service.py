import random
from typing import Any

from app.utils.rand import fisher_yates_shuffle_with_rng

GROUP_COUNT = 3
DRAW_COUNT = 8
REVERSED_PROBABILITY = 0.5


def split_into_three_groups(cards: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    if len(cards) < GROUP_COUNT:
        raise ValueError("Not enough cards to split")
    # 균등 분할(78장 기준 26장씩)
    size = len(cards) // 3
    a = cards[:size]
    b = cards[size : size * 2]
    c = cards[size * 2 :]
    return a, b, c


def merge_by_order(groups: tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]], order: list[str]) -> list[dict[str, Any]]:
    mapping = {"A": 0, "B": 1, "C": 2}
    merged: list[dict[str, Any]] = []
    for key in order:
        merged.extend(groups[mapping[key]])
    return merged


def shuffle_n_times(cards: list[dict[str, Any]], times: int, rng: random.Random) -> list[dict[str, Any]]:
    shuffled = list(cards)
    for _ in range(times):
        shuffled = fisher_yates_shuffle_with_rng(shuffled, rng)
    return shuffled


def draw_eight(cards: list[dict[str, Any]], rng: random.Random, allow_reversed: bool) -> list[dict[str, Any]]:
    if len(cards) < DRAW_COUNT:
        raise ValueError("Not enough cards in deck")
    drawn = []
    for idx, card in enumerate(cards[:DRAW_COUNT]):
        is_reversed = allow_reversed and (rng.random() < REVERSED_PROBABILITY)
        drawn.append({"position": idx + 1, "is_reversed": is_reversed, "card": card})
    return drawn


def create_reading(cards: list[dict[str, Any]], order: list[str], shuffle_times: int, seed: int | None, allow_reversed: bool):
    if len(cards) < DRAW_COUNT:
        raise ValueError("Not enough cards in deck")
    rng = random.Random(seed)
    groups = split_into_three_groups(cards)
    merged = merge_by_order(groups, order)
    shuffled = shuffle_n_times(merged, shuffle_times, rng)
    return draw_eight(shuffled, rng, allow_reversed)
