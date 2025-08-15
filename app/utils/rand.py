import random
from typing import Optional, TypeVar

T = TypeVar("T")


def fisher_yates_shuffle(items: list[T], seed: Optional[int] = None) -> list[T]:
    rng = random.Random(seed)
    arr = list(items)
    for i in range(len(arr) - 1, 0, -1):
        j = rng.randint(0, i)
        arr[i], arr[j] = arr[j], arr[i]
    return arr


def fisher_yates_shuffle_with_rng(items: list[T], rng: random.Random) -> list[T]:
    arr = list(items)
    for i in range(len(arr) - 1, 0, -1):
        j = rng.randint(0, i)
        arr[i], arr[j] = arr[j], arr[i]
    return arr
