import random
from typing import List, TypeVar, Optional

T = TypeVar("T")


def fisher_yates_shuffle(items: List[T], seed: Optional[int] = None) -> List[T]:
    rng = random.Random(seed)
    arr = list(items)
    for i in range(len(arr) - 1, 0, -1):
        j = rng.randint(0, i)
        arr[i], arr[j] = arr[j], arr[i]
    return arr


def fisher_yates_shuffle_with_rng(items: List[T], rng: random.Random) -> List[T]:
    arr = list(items)
    for i in range(len(arr) - 1, 0, -1):
        j = rng.randint(0, i)
        arr[i], arr[j] = arr[j], arr[i]
    return arr
