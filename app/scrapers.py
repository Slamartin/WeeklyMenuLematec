from __future__ import annotations

import re
import threading
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from io import BytesIO
from typing import Any
from urllib.parse import urljoin

import pdfplumber
import requests
from bs4 import BeautifulSoup


DAY_ORDER = ["monday", "tuesday", "wednesday", "thursday", "friday"]
DAY_NAME_MAP = {
    "pond\u011bl\u00ed": "monday",
    "\u00fater\u00fd": "tuesday",
    "st\u0159eda": "wednesday",
    "\u010dtvrtek": "thursday",
    "p\u00e1tek": "friday",
}
DAY_LINE_PATTERN = re.compile(
    r"^(Pond\u011bl\u00ed|\u00dater\u00fd|St\u0159eda|\u010ctvrtek|P\u00e1tek)\b(?:\s+\d{1,2}\.\d{1,2}\.?(?:\d{4})?)?$",
    re.IGNORECASE,
)
PRICE_ONLY_PATTERN = re.compile(r"^\d+(?:[,.]\d+)?\s*K\u010d$", re.IGNORECASE)
ALLERGEN_ONLY_PATTERN = re.compile(r"^[/(]?[Aa]lergeny?.*$|^/\d", re.IGNORECASE)
NOISE_PATTERN = re.compile(
    r"^(Objednat|Objedn\u00e1vka|St\u00e1hnout menu v PDF|Zm\u011bna menu vyhrazena|Pol\u00e9vka je ke ka\u017ed\u00e9mu j\u00eddlu zdarma).*$",
    re.IGNORECASE,
)
COOKPOINT_PDF_LINK_PATTERN = re.compile(r"/wp-content/uploads/.+\.pdf$", re.IGNORECASE)


class MenuScrapeError(RuntimeError):
    """Raised when a source cannot be scraped or parsed."""


@dataclass
class CacheEntry:
    expires_at: datetime
    payload: dict[str, Any]


class MenuCache:
    """Small in-memory TTL cache used by the API."""

    def __init__(self, ttl_hours: int = 6) -> None:
        self.ttl = timedelta(hours=ttl_hours)
        self._entry: CacheEntry | None = None
        self._lock = threading.Lock()

    def get(self) -> dict[str, Any] | None:
        with self._lock:
            if self._entry and self._entry.expires_at > datetime.now(UTC):
                return self._entry.payload
            return None

    def set(self, payload: dict[str, Any]) -> None:
        with self._lock:
            self._entry = CacheEntry(
                expires_at=datetime.now(UTC) + self.ttl,
                payload=payload,
            )


class WeeklyMenuService:
    def __init__(self) -> None:
        self.cache = MenuCache(ttl_hours=6)
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "WeeklyMenuBot/1.0 "
                    "(compatible; lunch-menu-aggregator; +https://localhost)"
                )
            }
        )

    def get_menu(self) -> dict[str, Any]:
        cached = self.cache.get()
        if cached:
            return cached

        errors: dict[str, str] = {}
        bistro_menu: dict[str, list[str]] = _empty_week()
        cookpoint_menu: dict[str, list[str]] = _empty_week()
        bistro_week_label = ""
        cookpoint_week_label = ""

        try:
            bistro_menu, bistro_week_label = self._fetch_bistro22()
        except Exception as exc:  # pragma: no cover - exercised through runtime usage
            errors["bistro22"] = str(exc)

        try:
            cookpoint_menu, cookpoint_week_label = self._fetch_cookpoint()
        except Exception as exc:  # pragma: no cover - exercised through runtime usage
            errors["cookpoint"] = str(exc)

        payload: dict[str, Any] = {
            "bistro22": bistro_menu,
            "cookpoint": cookpoint_menu,
            "_meta": {
                "generatedAt": datetime.now(UTC).isoformat(),
                "cacheTtlHours": 6,
                "weekLabel": bistro_week_label or cookpoint_week_label,
                "sourceWeekLabels": {
                    "bistro22": bistro_week_label,
                    "cookpoint": cookpoint_week_label,
                },
                "errors": errors,
            },
        }
        self.cache.set(payload)
        return payload

    def _fetch_bistro22(self) -> tuple[dict[str, list[str]], str]:
        response = self.session.get("https://bistro22.cz/", timeout=25)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        text = soup.get_text("\n")
        lines = _clean_lines(text)

        start_index = next(
            (index for index, line in enumerate(lines) if "tento t\u00fdden va\u0159\u00edme" in line.lower()),
            None,
        )
        if start_index is None:
            raise MenuScrapeError("Bistro 22 menu section was not found in the HTML.")

        relevant_lines = lines[start_index + 1 :]
        parsed = _parse_week_lines(
            relevant_lines,
            stop_markers=["t\u00fddenn\u00ed nab\u00eddka", "objednat j\u00eddlo"],
        )
        if not any(parsed["menu"].values()):
            raise MenuScrapeError("Bistro 22 weekly menu could not be parsed from the HTML section.")
        return parsed["menu"], parsed["week_label"]

    def _fetch_cookpoint(self) -> tuple[dict[str, list[str]], str]:
        response = self.session.get("https://www.cookpoint.cz/", timeout=25)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        pdf_url = self._find_cookpoint_pdf_link(soup)
        if not pdf_url:
            raise MenuScrapeError("Cookpoint weekly PDF link was not found on the homepage.")

        pdf_response = self.session.get(pdf_url, timeout=40)
        pdf_response.raise_for_status()

        pdf_text_parts: list[str] = []
        with pdfplumber.open(BytesIO(pdf_response.content)) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text(x_tolerance=2, y_tolerance=2) or ""
                if page_text.strip():
                    pdf_text_parts.append(page_text)

        if not pdf_text_parts:
            raise MenuScrapeError("Cookpoint weekly PDF did not contain extractable text.")

        parsed = _parse_week_lines(_clean_lines("\n".join(pdf_text_parts)))
        if not any(parsed["menu"].values()):
            raise MenuScrapeError("Cookpoint weekly PDF was downloaded, but the menu could not be parsed.")
        return parsed["menu"], parsed["week_label"]

    def _find_cookpoint_pdf_link(self, soup: BeautifulSoup) -> str | None:
        for anchor in soup.find_all("a", href=True):
            href = anchor["href"].strip()
            label = " ".join(anchor.stripped_strings).lower()
            if "t\u00fddenn\u00ed menu" in label and href.lower().endswith(".pdf"):
                return urljoin("https://www.cookpoint.cz/", href)
            if COOKPOINT_PDF_LINK_PATTERN.search(href):
                return urljoin("https://www.cookpoint.cz/", href)
        return None


def _empty_week() -> dict[str, list[str]]:
    return {day: [] for day in DAY_ORDER}


def _clean_lines(text: str) -> list[str]:
    replacements = {
        "\xa0": " ",
        "ﬂ": "fl",
        "ﬁ": "fi",
        "ơ": "t",
        "„": '"',
        "“": '"',
        "”": '"',
    }
    for original, replacement in replacements.items():
        text = text.replace(original, replacement)

    cleaned_lines: list[str] = []
    for raw_line in text.splitlines():
        line = re.sub(r"\s+", " ", raw_line).strip(" -\t")
        if line:
            cleaned_lines.append(line)
    return cleaned_lines


def _parse_week_lines(lines: list[str], stop_markers: list[str] | None = None) -> dict[str, Any]:
    menu = _empty_week()
    current_day: str | None = None
    week_dates: list[str] = []

    stop_markers = stop_markers or []

    for line in lines:
        lowered = line.lower()
        if any(marker in lowered for marker in stop_markers):
            break
        if NOISE_PATTERN.match(line):
            continue

        day_match = DAY_LINE_PATTERN.match(line)
        if day_match:
            current_day = DAY_NAME_MAP[day_match.group(1).lower()]
            date_match = re.search(r"(\d{1,2}\.\d{1,2}\.?(?:\d{4})?)", line)
            if date_match:
                week_dates.append(date_match.group(1))
            continue

        if not current_day:
            continue
        if ALLERGEN_ONLY_PATTERN.match(line):
            continue

        normalized_line = _normalize_menu_line(line)
        if not normalized_line:
            continue

        if PRICE_ONLY_PATTERN.match(normalized_line):
            if menu[current_day]:
                menu[current_day][-1] = f"{menu[current_day][-1]} - {normalized_line}"
            continue

        menu[current_day].append(normalized_line)

    week_label = ""
    if week_dates:
        week_label = f"{week_dates[0]} - {week_dates[-1]}"

    return {"menu": menu, "week_label": week_label}


def _normalize_menu_line(line: str) -> str:
    line = re.sub(r"\s+", " ", line).strip(" -")
    if not line:
        return ""

    line = re.sub(r"\s+\(\s+", " (", line)
    line = re.sub(r"\s+\)", ")", line)
    line = re.sub(r"\s+,", ",", line)
    line = re.sub(r"\s+K\u010d", " K\u010d", line, flags=re.IGNORECASE)

    if line.isdigit():
        return ""
    return line

