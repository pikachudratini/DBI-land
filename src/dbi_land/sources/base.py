from __future__ import annotations

from typing import Iterable, Protocol

from dbi_land.models import Listing


class Source(Protocol):
    name: str

    def fetch(self) -> Iterable[Listing]:
        ...
