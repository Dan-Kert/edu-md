import logging
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup

from .utils import DEFAULT_HEADERS, LANGUAGE_ALIASES, REQUEST_DELAY_SECONDS, detect_language, detect_subject, polite_get
from .progress import format_crawl_progress, print_progress_update, complete_progress_line, print_warning

logger = logging.getLogger(__name__)

ANCE_FILENAME_RE = re.compile(
    r"^(?P<class>\d{1,2})_(?P<subject>[a-z]+)_(?P<kind>test|barem)(?P<kind_variant>\d?)_(?:(?P<track>[ru])_)?(?:(?P<lang>[a-z]{2})_)?(?P<session>[a-z]+)(?P<year>\d{2})\.pdf$",
    re.IGNORECASE,
)
SUBJECT_CODE_TO_SUBJECT = {
    "ist": "istorie",
    "mat": "matematica",
    "llro": "limba romana",
    "llroal": "limba romana",
    "llru": "limba rusa",
    "llbg": "limba bulgara",
    "llgag": "limba gagauza",
    "llucr": "limba ucraineana",
    "geo": "geografie",
    "bio": "biologie",
    "chi": "chimie",
    "chim": "chimie",
    "fiz": "fizica",
    "inf": "informatica",
    "lfr": "limba franceza",
    "lfrbil": "limba franceza (bilingv)",
    "lger": "limba germana",
    "lspa": "limba spaniola",
    "ltur": "limba turca",
    "coregrafie": "coregrafie",
    "litt": "literatura",
    "len": "limba engleza",
    "lit": "literatura",
    "cult": "cultura",
    "prsp": "pregatire sportiva",
    "istartpl": "istoria artei plastice",
    "istartteatr": "istoria artei teatrale",
    "istdansbulg": "istoria dansului bulgar",
}
LANGUAGE_CODE_TO_LANGUAGE = {
    "ro": "romanian",
    "ru": "russian",
    "en": "english",
    "fr": "french",
    "bg": "bulgarian",
    "gag": "gagauz",
    "ucr": "ukrainian",
}

class AnceParser:
    def __init__(self, url: str, session: Optional[requests.Session] = None, request_delay: float = REQUEST_DELAY_SECONDS) -> None:
        self.url = url
        self.session = session or requests.Session()
        self.request_delay = request_delay

    def fetch_html(self) -> str:
        response = polite_get(
            self.session,
            self.url,
            delay_seconds=self.request_delay,
            headers=DEFAULT_HEADERS,
            timeout=30,
        )
        return response.text

    def parse_html(self, html: str) -> List[Dict[str, Any]]:
        soup = BeautifulSoup(html, "html.parser")
        records: List[Dict[str, Any]] = []
        seen_urls: set[str] = set()
        for link in soup.select("a[href]"):
            href = link.get("href", "")
            if not href or href.startswith("#") or "javascript" in href:
                continue
            full_url = href if href.startswith("http") else urljoin(self.url, href)
            if not any(full_url.lower().endswith(ext) for ext in [".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".odt", ".rtf"]):
                continue
            if full_url in seen_urls:
                continue
            seen_urls.add(full_url)
            title = " ".join(link.get_text(" ", strip=True).split())
            filename = Path(full_url).name
            parsed_filename = self.parse_ance_filename(filename)
            class_number = None
            if parsed_filename is not None:
                class_number = parsed_filename["class_number"]
            if class_number is None:
                class_number = self._extract_class_from_url(full_url)
            if class_number is None:
                class_number = self._extract_class_from_filename(Path(full_url).name)
            if class_number is None:
                class_number = self._extract_class_from_text(title)

            subject = self._detect_subject_from_url(full_url)
            if subject == "other":
                subject = detect_subject(title)
            language = self._detect_language_from_url(full_url)
            if language == "unknown":
                language = detect_language(title)
            records.append(
                {
                    "class_name": f"Clasa {class_number}" if class_number is not None else "",
                    "class_number": class_number,
                    "title": title,
                    "language": language,
                    "subject": subject,
                    "url": full_url,
                    "filename": filename,
                    "kind": parsed_filename["kind"] if parsed_filename else None,
                    "kind_variant": parsed_filename["kind_variant"] if parsed_filename else None,
                }
            )
        return records

    def fetch_tests(self, visited: Optional[set] = None, progress_counter: Optional[Dict[str, int]] = None) -> List[Dict[str, Any]]:
        if visited is None:
            visited = set()
        if progress_counter is None:
            progress_counter = {"count": 0, "is_root": True}
        else:
            progress_counter["is_root"] = False
            
        if self.url in visited:
            return []
        visited.add(self.url)
        progress_counter["count"] += 1
        
        # Print progress if this is the root call or every few items
        if progress_counter["count"] % 5 == 0 or progress_counter.get("is_root"):
            print_progress_update(format_crawl_progress("ance", progress_counter["count"]))

        html = self.fetch_html()
        direct_records = self.parse_html(html)

        soup = BeautifulSoup(html, "html.parser")
        linked_urls: List[str] = []
        for link in soup.select("a[href]"):
            href = link.get("href", "")
            if not href or href.startswith("#") or "javascript" in href:
                continue
            full_url = href if href.startswith("http") else urljoin(self.url, href)
            if "sesiunea" in full_url.lower() or "clasa-" in full_url.lower() or "class-" in full_url.lower():
                linked_urls.append(full_url)

        records: List[Dict[str, Any]] = []
        if direct_records:
            records.extend(direct_records)
        for linked_url in dict.fromkeys(linked_urls):
            try:
                nested_parser = AnceParser(url=linked_url, session=self.session, request_delay=self.request_delay)
                records.extend(nested_parser.fetch_tests(visited=visited, progress_counter=progress_counter))
            except Exception as exc:
                print_warning("ance", f"Skipped nested URL {linked_url}: {exc}")
                continue
        
        # Complete progress line if this is root call
        if progress_counter.get("is_root"):
            complete_progress_line()
            
        return records

    @staticmethod
    def _extract_class_from_url(url: str) -> Optional[int]:
        match = re.search(r"/(?:clasa|class)-?(\d+)", url, re.I)
        if match:
            return int(match.group(1))
        return None

    @staticmethod
    def _extract_class_from_filename(filename: str) -> Optional[int]:
        match = re.search(r"(?:^|[_/-])(?P<value>0?[4-9]|1[0-2])(?=[_/-]|$)", filename)
        if match:
            return int(match.group("value"))
        return None

    @staticmethod
    def _extract_class_from_text(text: str) -> Optional[int]:
        match = re.search(r"\b(?:clasa|class)\s*([4-9]|1[0-2])\b", text, re.I)
        if match:
            return int(match.group(1))
        return None

    @staticmethod
    @lru_cache(maxsize=None)
    def discover_ance_session_urls(class_number: int) -> Dict[int, List[str]]:
        if class_number not in {4, 9, 12}:
            raise ValueError("ANCE class number must be one of 4, 9, 12")

        page_url = f"https://ance.gov.md/clasa-sesiunea-examen/clasa-{class_number}"
        session = requests.Session()
        response = polite_get(session, page_url, headers=DEFAULT_HEADERS, timeout=30)

        soup = BeautifulSoup(response.text, "html.parser")
        urls_by_year: Dict[int, List[str]] = {}
        for link in soup.select("a[href]"):
            href = link.get("href", "").strip()
            if not href or href.startswith("#") or "javascript" in href.lower():
                continue
            full_url = href if href.startswith("http") else urljoin("https://ance.gov.md/", href)
            if "clasa-sesiunea-examen/sesiunea-" not in full_url.lower() and "clasa-" not in full_url.lower() and "sesiunea-" not in full_url.lower():
                continue
            match = re.search(r"sesiunea-(\d{4})(?:[A-Za-z0-9-]+)?(?:/|$)", full_url, re.I)
            if not match:
                continue
            year = int(match.group(1))
            urls_by_year.setdefault(year, [])
            if full_url not in urls_by_year[year]:
                urls_by_year[year].append(full_url)
        return urls_by_year

    @staticmethod
    def parse_ance_filename(filename: str) -> Optional[Dict[str, Any]]:
        name = Path(filename).name
        match = ANCE_FILENAME_RE.match(name)
        if not match:
            return None

        data = match.groupdict()
        class_number = int(data["class"])
        subject_code = data["subject"].lower()
        language_code = (data.get("lang") or "").lower() or None
        session_code = data["session"].lower()
        year = data["year"]
        subject = SUBJECT_CODE_TO_SUBJECT.get(subject_code, subject_code)
        if subject_code in {"llro", "llroal"} and not language_code:
            language = "romanian"
        elif subject_code == "llru" and not language_code:
            language = "russian"
        elif subject_code == "llbg" and not language_code:
            language = "bulgarian"
        elif subject_code == "llgag" and not language_code:
            language = "gagauz"
        elif subject_code == "llucr" and not language_code:
            language = "ukrainian"
        else:
            language = LANGUAGE_CODE_TO_LANGUAGE.get(language_code, "unknown")

        return {
            "class_number": class_number,
            "subject_code": subject_code,
            "kind": data["kind"].lower(),
            "kind_variant": data["kind_variant"] or "",
            "track": (data.get("track") or "").lower(),
            "language_code": language_code,
            "session_code": session_code,
            "year": year,
            "subject": subject,
            "language": language,
        }

    @staticmethod
    def _detect_subject_from_url(url: str) -> str:
        filename = Path(url).name.lower()
        parsed = AnceParser.parse_ance_filename(filename)
        if parsed:
            return parsed["subject"]

        lower = url.lower()
        for token, subject in SUBJECT_CODE_TO_SUBJECT.items():
            if token in filename or token in lower:
                return subject
        if any(token in lower for token in ["llro", "llroal", "limba romana", "limba-romana"]):
            return "limba romana"
        if any(token in lower for token in ["llru", "limba rusa", "limba-rusa"]):
            return "limba rusa"
        if "limba" in filename or "limba" in lower:
            return "limba romana"
        return "other"

    @staticmethod
    def _detect_language_from_url(url: str) -> str:
        filename = Path(url).name.lower()
        parsed = AnceParser.parse_ance_filename(filename)
        if parsed:
            return parsed["language"]

        lower = url.lower()
        long_aliases = sorted(
            ((token, canonical) for token, canonical in LANGUAGE_ALIASES.items() if token not in {"all"} and len(token) > 2),
            key=lambda item: len(item[0]),
            reverse=True,
        )
        for token, canonical in long_aliases:
            if token in lower:
                return canonical

        short_aliases = [
            (token, canonical)
            for token, canonical in LANGUAGE_ALIASES.items()
            if token not in {"all"} and len(token) == 2
        ]
        for token, canonical in short_aliases:
            if re.search(rf"(?<![a-z]){re.escape(token)}(?![a-z])", lower):
                return canonical

        for token in ("_ro_", "llro", "llroal", "limba-romana", "limba_ro", "limba romana"):
            if token in lower:
                return "romanian"
        for token in ("_ru_", "llru", "limba-rusa", "limba_ru", "limba rusa"):
            if token in lower:
                return "russian"
        for token in ("_bg_", "llbg", "limba-bulgara", "limba_bg", "limba bulgara", "bulgar"):
            if token in lower:
                return "bulgarian"
        for token in ("_gag_", "llgag", "limba-gagauza", "limba_gagauza", "limba gagauza"):
            if token in lower:
                return "gagauz"
        for token in ("_ucr_", "llucr", "limba-ucraineana", "limba_ucr", "limba ucraineana", "ucrain"):
            if token in lower:
                return "ukrainian"
        return "unknown"