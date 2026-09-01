import re
from collections import deque
from typing import Any, Deque, Dict, List, Optional, Set, Tuple
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from .utils import DEFAULT_HEADERS, detect_language, detect_subject, polite_get
from .progress import format_crawl_progress, print_progress_update, complete_progress_line, print_warning

RESOURCE_TYPE_ALIASES = {
    "video": {"video", "mp4", "mkv", "avi", "mov", "webm", "youtube", "lesson", "lecture"},
    "audio": {"audio", "mp3", "wav", "ogg", "podcast"},
    "pdf": {"pdf", "book", "manual", "guide", "textbook", "lesson-book", "ebook"},
    "doc": {"doc", "docx", "odt", "rtf", "ppt", "pptx", "xls", "xlsx", "txt"},
    "archive": {"zip", "rar", "7z", "tar", "gz", "bz2"},
    "image": {"image", "jpg", "jpeg", "png", "svg", "gif"},
    "html": {"html", "webpage", "page"},
}

class EduResurseParser:
    def __init__(self, url: str, request_delay: float = 2.5) -> None:
        self.url = url
        self.request_delay = request_delay

    @staticmethod
    def detect_resource_type(record: Dict[str, Any]) -> str:
        text = " ".join(
            str(record.get(field, "") or "")
            for field in ["title", "filename", "url", "subject", "class_name", "download_url"]
        ).lower()
        for resource_type, markers in RESOURCE_TYPE_ALIASES.items():
            if any(marker in text for marker in markers):
                return resource_type
        if "/download" in text:
            return "download"
        return "other"

    @staticmethod
    def _normalize_url(base_url: str, href: str) -> str:
        if not href:
            return ""
        href = href.strip()
        if href.startswith("javascript:") or href.startswith("#"):
            return ""
        if href.startswith("//"):
            href = "https:" + href
        return urljoin(base_url, href)

    @staticmethod
    def _safe_title_from_url(url: str) -> str:
        path = urlparse(url).path.rstrip("/")
        if not path:
            return "EduResurse resource"
        slug = path.rsplit("/", 1)[-1]
        if not slug:
            return "EduResurse resource"
        return slug.replace("-", " ").replace("_", " ").title()

    @staticmethod
    def _extract_class_number(title: str) -> Optional[int]:
        if not title:
            return None
        lower = title.lower()
        for roman, value in {"iv": 4, "v": 5, "vi": 6, "vii": 7, "viii": 8, "ix": 9, "x": 10, "xi": 11, "xii": 12}.items():
            if f"clasa {roman}" in lower or f"clasa a {roman}" in lower or f"class {roman}" in lower:
                return value
        match = re.search(r"(?:class|clasa)\s*(?:a\s*)?(\d+)", title, flags=re.IGNORECASE)
        if match:
            return int(match.group(1))
        return None

    def fetch_html(self, url: Optional[str] = None) -> str:
        session = requests.Session()
        target = url or self.url
        response = polite_get(
            session,
            target,
            delay_seconds=self.request_delay,
            headers=DEFAULT_HEADERS,
            timeout=30,
        )
        return response.text

    def parse_html(self, html: str, base_url: Optional[str] = None) -> List[Dict[str, Any]]:
        base_url = base_url or self.url
        soup = BeautifulSoup(html, "html.parser")
        records: List[Dict[str, Any]] = []
        seen: Set[str] = set()

        for link in soup.select("a[href]"):
            href = self._normalize_url(base_url, link.get("href", ""))
            if not href or "eduresurse.gov.md" not in href:
                continue

            resource_path = urlparse(href).path.rstrip("/")
            if not resource_path or "/resource/" not in resource_path:
                continue
            if resource_path.endswith("/download") or resource_path.endswith("/preview"):
                continue

            if href in seen:
                continue
            seen.add(href)

            title = " ".join(link.get_text(" ", strip=True).split())
            if not title:
                title = self._safe_title_from_url(href)
            class_number = self._extract_class_number(title)
            filename = title or self._safe_title_from_url(href)

            download_url = self._normalize_url(base_url, f"{resource_path}/download")
            preview_url = self._normalize_url(base_url, f"{resource_path}/preview")
            record = {
                "class_name": f"Clasa a {class_number}-a" if class_number else "",
                "class_number": class_number,
                "title": title,
                "language": detect_language(title),
                "subject": detect_subject(title),
                "url": href,
                "download_url": download_url,
                "preview_url": preview_url,
                "filename": filename,
                "resource_type": "other",
            }
            record["resource_type"] = self.detect_resource_type(record)
            records.append(record)

        return records

    def fetch_resources(self) -> List[Dict[str, Any]]:
        queue: Deque[Tuple[str, int]] = deque([(self.url, 0)])
        visited: Set[str] = set()
        results: List[Dict[str, Any]] = []
        seen_urls: Set[str] = set()
        max_depth = 6
        total_pages = 0
        total_records = 0

        print(f"Start EduResurse crawl: {self.url}")
        while queue:
            current_url, depth = queue.popleft()
            if current_url in visited or depth > max_depth:
                continue
            visited.add(current_url)
            total_pages += 1
            
            # Use progress bar for crawl status
            print_progress_update(format_crawl_progress("eduresurse", total_pages))

            try:
                html = self.fetch_html(current_url)
            except Exception as exc:
                print_warning("eduresurse", f"skipped URL {current_url}: {exc}")
                continue

            page_records = self.parse_html(html, base_url=current_url)
            if page_records:
                total_records += len(page_records)
            for record in page_records:
                key = record["url"]
                if key not in seen_urls:
                    seen_urls.add(key)
                    results.append(record)

            soup = BeautifulSoup(html, "html.parser")
            discovered = 0
            for link in soup.select("a[href]"):
                href = self._normalize_url(current_url, link.get("href", ""))
                if not href or "eduresurse.gov.md" not in href:
                    continue
                if "/resource/" in href:
                    continue
                if "/catalog" not in href:
                    continue
                if href not in visited and href not in {item[0] for item in queue}:
                    queue.append((href, depth + 1))
                    discovered += 1

        # Complete the progress line and print summary
        complete_progress_line()
        print(f"EduResurse crawl finished: {len(results)} unique resource entries discovered across {total_pages} pages.")
        return results

    @staticmethod
    def filter_resources(
        records: List[Dict[str, Any]],
        classes: Optional[List[int]] = None,
        keywords: Optional[List[str]] = None,
        languages: Optional[List[str]] = None,
        resource_types: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        normalized_classes = {int(item) for item in (classes or [])}
        normalized_keywords = [item.lower() for item in (keywords or []) if item]
        normalized_languages = {item.lower() for item in (languages or []) if item}
        normalized_types = {item.lower() for item in (resource_types or []) if item}

        filtered: List[Dict[str, Any]] = []
        for record in records:
            record["resource_type"] = record.get("resource_type") or EduResurseParser.detect_resource_type(record)
            if normalized_classes and record.get("class_number") not in normalized_classes:
                continue
            if normalized_keywords:
                haystack = " ".join(
                    str(record.get(field, "") or "")
                    for field in ["title", "subject", "class_name", "url", "filename"]
                ).lower()
                if not any(keyword.lower() in haystack for keyword in normalized_keywords):
                    continue
            if normalized_languages and record.get("language", "unknown").lower() not in normalized_languages:
                continue
            if normalized_types and record.get("resource_type", "other").lower() not in normalized_types:
                continue
            filtered.append(record)
        return filtered