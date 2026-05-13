from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class AcreageBand:
    min_acres: float
    max_acres: float
    weight: float = 1.0

    def contains(self, acres: float) -> bool:
        return self.min_acres <= acres <= self.max_acres


@dataclass(frozen=True)
class PriceCeiling:
    max_price_per_acre: float
    max_total_price: float


@dataclass(frozen=True)
class Criteria:
    states: tuple[str, ...]
    acreage_bands: tuple[AcreageBand, ...]
    price: PriceCeiling
    min_water_score: float = 0.0
    min_road_access_score: float = 0.0
    min_power_proximity_score: float = 0.0
    min_tower_proximity_score: float = 0.0
    weights: dict[str, float] = field(default_factory=dict)
    excluded_counties: tuple[str, ...] = ()

    @classmethod
    def from_yaml(cls, path: str | Path) -> "Criteria":
        data = yaml.safe_load(Path(path).read_text())
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Criteria":
        bands = tuple(
            AcreageBand(
                min_acres=b["min_acres"],
                max_acres=b["max_acres"],
                weight=b.get("weight", 1.0),
            )
            for b in data["acreage_bands"]
        )
        price = PriceCeiling(
            max_price_per_acre=data["price"]["max_per_acre"],
            max_total_price=data["price"]["max_total"],
        )
        return cls(
            states=tuple(s.upper() for s in data["states"]),
            acreage_bands=bands,
            price=price,
            min_water_score=data.get("min_water_score", 0.0),
            min_road_access_score=data.get("min_road_access_score", 0.0),
            min_power_proximity_score=data.get("min_power_proximity_score", 0.0),
            min_tower_proximity_score=data.get("min_tower_proximity_score", 0.0),
            weights=dict(data.get("weights", {})),
            excluded_counties=tuple(data.get("excluded_counties", [])),
        )

    def weight(self, name: str, default: float = 1.0) -> float:
        return float(self.weights.get(name, default))

    def best_band(self, acres: float) -> AcreageBand | None:
        for band in self.acreage_bands:
            if band.contains(acres):
                return band
        return None
