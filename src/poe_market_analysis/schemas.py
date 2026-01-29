from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from enum import Enum
from pathlib import Path
from typing import Callable, Iterable, Optional, Sequence, TypeVar

CSV_DELIMITER = ";"


class ConfidenceLevel(str, Enum):
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class LinksCategory(str, Enum):
    ONE_TO_FOUR = "1-4 links"
    FIVE = "5 links"
    SIX = "6 links"


@dataclass(frozen=True)
class CurrencyRow:
    league: str
    date: date
    get: str
    pay: str
    value: float
    confidence: ConfidenceLevel

    @classmethod
    def from_row(cls, row: dict[str, str]) -> "CurrencyRow":
        return cls(
            league=row["League"],
            date=_parse_date(row["Date"]),
            get=row["Get"],
            pay=row["Pay"],
            value=float(row["Value"]),
            confidence=ConfidenceLevel(row["Confidence"]),
        )


@dataclass(frozen=True)
class ItemRow:
    league: str
    date: date
    id: int
    type: str
    name: str
    base_type: str
    variant: Optional[str]
    links: Optional[LinksCategory]
    value: float
    confidence: ConfidenceLevel

    @classmethod
    def from_row(cls, row: dict[str, str]) -> "ItemRow":
        return cls(
            league=row["League"],
            date=_parse_date(row["Date"]),
            id=int(row["Id"]),
            type=row["Type"],
            name=row["Name"],
            base_type=row["BaseType"],
            variant=_empty_to_none(row["Variant"]),
            links=_parse_links(row["Links"]),
            value=float(row["Value"]),
            confidence=ConfidenceLevel(row["Confidence"]),
        )


@dataclass(frozen=True)
class CsvSchema:
    name: str
    columns: Sequence[str]


CURRENCY_SCHEMA = CsvSchema(
    name="currency",
    columns=("League", "Date", "Get", "Pay", "Value", "Confidence"),
)

ITEMS_SCHEMA = CsvSchema(
    name="items",
    columns=(
        "League",
        "Date",
        "Id",
        "Type",
        "Name",
        "BaseType",
        "Variant",
        "Links",
        "Value",
        "Confidence",
    ),
)


T = TypeVar("T")


def read_currency_rows(path: Path | str) -> Iterable[CurrencyRow]:
    return _read_rows(path, CurrencyRow.from_row)


def read_item_rows(path: Path | str) -> Iterable[ItemRow]:
    return _read_rows(path, ItemRow.from_row)


def _read_rows(path: Path | str, row_parser: Callable[[dict[str, str]], T]) -> Iterable[T]:
    with open(path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter=CSV_DELIMITER)
        for row in reader:
            yield row_parser(row)


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def _empty_to_none(value: str) -> Optional[str]:
    return value or None


def _parse_links(value: str) -> Optional[LinksCategory]:
    if not value:
        return None
    return LinksCategory(value)
