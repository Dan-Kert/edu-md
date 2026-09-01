import argparse
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence
import time
import requests
from bs4 import BeautifulSoup
import urllib3

from .config import CTICE_URL, subject_aliases_for_source
from .utils import (
    DEFAULT_HEADERS,
    detect_language,
    detect_subject,
    extract_class_number,
    normalize_class_name,
    polite_get,
    roman_to_int,
)
from .progress import format_download_progress, complete_progress_line

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class CticeParser:
    def __init__(self, url: str = CTICE_URL, request_delay: float = 2.5) -> None:
        self.url = url
        self.request_delay = request_delay

    def fetch_html(self) -> str:
        session = requests.Session()
        response = polite_get(
            session,
            self.url,
            delay_seconds=self.request_delay,
            headers=DEFAULT_HEADERS,
            timeout=30,
        )
        return response.text

    def parse_html(self, html: str) -> List[Dict[str, Any]]:
        soup = BeautifulSoup(html, "html.parser")
        books: List[Dict[str, Any]] = []
        for category_item in soup.select("main li"):
            if not category_item.find("ul", class_="bookClass"):
                continue
            folder_div = category_item.find("div")
            if not folder_div:
                continue
            class_name = normalize_class_name(folder_div.get_text(" ", strip=True))
            for pdf_item in category_item.select("ul.bookClass > li"):
                link = pdf_item.find("a")
                if not link:
                    continue
                title = " ".join(link.get_text(" ", strip=True).split())
                class_number = extract_class_number(class_name, title)
                books.append(
                    {
                        "class_name": class_name,
                        "class_number": class_number,
                        "title": title,
                        "language": detect_language(title),
                        "subject": detect_subject(title),
                        "url": link.get("href", ""),
                        "filename": title,
                    }
                )
        return books

    def fetch_books(self) -> List[Dict[str, Any]]:
        return self.parse_html(self.fetch_html())

    def filter_books(
        self,
        books: Sequence[Dict[str, Any]],
        classes: Optional[Sequence[int]] = None,
        keywords: Optional[Sequence[str]] = None,
        languages: Optional[Sequence[str]] = None,
    ) -> List[Dict[str, Any]]:
        normalized_classes = {int(item) for item in (classes or [])}
        normalized_keywords = [item.lower() for item in (keywords or []) if item]
        normalized_languages = {item.lower() for item in (languages or []) if item}

        filtered: List[Dict[str, Any]] = []
        for book in books:
            if normalized_classes and book.get("class_number") not in normalized_classes:
                continue
            if normalized_keywords:
                haystack = f"{book.get('title','')} {book.get('subject','')} {book.get('class_name','')}".lower()
                if not any(keyword.lower() in haystack for keyword in normalized_keywords):
                    continue
            if normalized_languages and book.get("language", "unknown").lower() not in normalized_languages:
                continue
            filtered.append(book)
        return filtered

def save_output(records: Sequence[Dict[str, Any]], output_path: Optional[str], output_format: str) -> None:
    if not output_path:
        return
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Only JSON format is supported
    path.write_text(json.dumps(list(records), ensure_ascii=False, indent=2), encoding="utf-8")

def download_books(
    records: Sequence[Dict[str, Any]],
    download_dir: str,
    max_workers: int = 1,
    delay_seconds: float = 3.0,
    insecure_ssl: bool = False,
) -> List[Path]:
    download_path = Path(download_dir)
    download_path.mkdir(parents=True, exist_ok=True)
    saved: List[Path] = []
    total = max(1, len(records))
    
    if insecure_ssl:
        print("WARNING: SSL certificate verification fallback is enabled. This reduces security.", file=sys.stderr)

    def download_record(record: Dict[str, Any]) -> Optional[Path]:
        url = record.get("download_url") or record.get("url", "")
        if not url:
            return None
        filename = record.get("filename") or Path(url).name or f"{record.get('class_number', 'manual')}.pdf"
        title = str(record.get("title") or filename)
        safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", filename)[:180]
        target = download_path / safe_name
        try:
            response = requests.get(url, headers=DEFAULT_HEADERS, timeout=60, verify=True)
            response.raise_for_status()
            target.write_bytes(response.content)
            return target
        except requests.exceptions.SSLError:
            if not insecure_ssl:
                raise
            print("SSL certificate check failed for the site, retrying without certificate verification", file=sys.stderr)
            try:
                response = requests.get(url, headers=DEFAULT_HEADERS, timeout=60, verify=False)
                response.raise_for_status()
                target.write_bytes(response.content)
                return target
            except Exception as e:
                print(f"Error downloading {title}: {e}", file=sys.stderr)
                return None
        except KeyboardInterrupt:
            print("\nDownload interrupted by user.", file=sys.stderr)
            raise
        except Exception as e:
            print(f"Error downloading {title}: {e}", file=sys.stderr)
            return None

    effective_workers = max(1, int(max_workers))
    effective_delay = max(0.0, float(delay_seconds))
    try:
        if len(records) <= 1 or effective_workers == 1:
            for index, record in enumerate(records, start=1):
                title = str(record.get("title") or record.get("filename") or f"file_{index}")
                print(f"\r{format_download_progress(int((index / total) * 100), title)}", end="", flush=True)
                result = download_record(record)
                if result:
                    saved.append(result)
                if effective_delay > 0 and index < len(records):
                    time.sleep(effective_delay)
            complete_progress_line()
            return saved

        completed = 0
        with ThreadPoolExecutor(max_workers=effective_workers) as executor:
            futures = {executor.submit(download_record, record): record for record in records}
            for future in as_completed(futures):
                completed += 1
                record = futures[future]
                title = str(record.get("title") or record.get("filename") or "Downloading file")
                print(f"\r{format_download_progress(int((completed / total) * 100), title)}", end="", flush=True)
                result = future.result()
                if result:
                    saved.append(result)
                if effective_delay > 0:
                    time.sleep(effective_delay)
        complete_progress_line()
        return saved
    except KeyboardInterrupt:
        print("\nDownload interrupted by user.", file=sys.stderr)
        return saved

def _record_matches_keywords(record: Dict[str, Any], keywords: Sequence[str]) -> bool:
    if not keywords:
        return True
    positive = []
    negative = []
    for token in keywords:
        if not token:
            continue
        normalized = token.strip()
        if normalized.startswith("!") or normalized.startswith("-"):
            value = normalized[1:].strip().lower()
            if value:
                negative.append(value)
        else:
            positive.append(normalized.lower())

    haystack = " ".join(
        str(record.get(field, "") or "") for field in ["title", "subject", "class_name", "url", "filename"]
    ).lower()
    for term in negative:
        if term and term in haystack:
            return False
    for term in positive:
        if term and term not in haystack:
            return False
    return True

def _record_matches_subjects(record: Dict[str, Any], subjects: Sequence[str], source: str = "ctice") -> bool:
    if not subjects:
        return True
    normalized = set()
    for item in subjects:
        if not item:
            continue
        normalized.add(str(item).strip().lower())
        normalized.update(subject_aliases_for_source(str(item), source=source))
    if not normalized:
        return True

    haystack = " ".join(
        str(record.get(field, "") or "") for field in ["title", "subject", "class_name", "url", "filename"]
    ).lower()
    for subject in normalized:
        if subject in haystack:
            return True
    return False

def _record_matches_kind(record: Dict[str, Any], kind: Optional[str]) -> bool:
    if not kind:
        return True

    explicit_kind = str(record.get("kind") or "")
    if explicit_kind:
        return explicit_kind.startswith(kind)

    haystack = " ".join(
        str(record.get(field, "") or "") for field in ["title", "filename", "url"]
    ).lower()
    if kind == "barem":
        return "barem" in haystack
    if kind == "test":
        return "test" in haystack and "barem" not in haystack
    return True

def run(
    args: argparse.Namespace,
    classes: Optional[Sequence[int]] = None,
    keywords: Optional[Sequence[str]] = None,
    subjects: Optional[Sequence[str]] = None,
    languages: Optional[Sequence[str]] = None,
    kind: Optional[str] = None,
) -> None:
    if "ance.gov.md" in args.url:
        from .ance import AnceParser

        print(f"Starting ANCE fetch: {args.url}")
        parser = AnceParser(url=args.url, request_delay=getattr(args, "request_delay", 2.5))
        records = parser.fetch_tests()
        print(f"ANCE fetch completed: {len(records)} records discovered.")
        filtered = []
        for record in records:
            if classes and record.get("class_number") not in set(classes):
                continue
            if not _record_matches_keywords(record, keywords or []):
                continue
            if not _record_matches_subjects(record, subjects or [], source="ance"):
                continue
            if not _record_matches_kind(record, kind):
                continue
            if languages and record.get("language", "unknown").lower() not in {lang.lower() for lang in languages}:
                continue
            filtered.append(record)
    elif "eduresurse.gov.md" in args.url:
        from .eduresurse import EduResurseParser

        print(f"Starting EduResurse fetch: {args.url}")
        parser = EduResurseParser(url=args.url, request_delay=getattr(args, "request_delay", 2.5))
        records = parser.fetch_resources()
        print(f"EduResurse fetch completed: {len(records)} records discovered.")
        resource_types_value = getattr(args, "resource_types", None)
        if isinstance(resource_types_value, str):
            resource_types_value = [item.strip().lower() for item in resource_types_value.split(",") if item.strip()]
        filtered = parser.filter_resources(
            records,
            classes=list(classes) if classes else None,
            keywords=list(keywords) if keywords else None,
            languages=list(languages) if languages else None,
            resource_types=list(resource_types_value) if resource_types_value else None,
        )
        if subjects:
            filtered = [record for record in filtered if _record_matches_subjects(record, subjects, source="ctice")]
    else:
        print(f"Starting CTICE fetch: {args.url}")
        parser = CticeParser(url=args.url, request_delay=getattr(args, "request_delay", 2.5))
        books = parser.fetch_books()
        print(f"CTICE fetch completed: {len(books)} records discovered.")
        filtered = parser.filter_books(books, classes=classes, keywords=keywords, languages=languages)
        if subjects:
            filtered = [record for record in filtered if _record_matches_subjects(record, subjects, source="ctice")]

    print(f"Parsing source: {args.url}")
    if args.format == "json":
        payload = json.dumps(filtered, ensure_ascii=False, indent=2)
        if args.output:
            save_output(filtered, args.output, args.format)
        else:
            print(payload)
    else:
        if args.output:
            save_output(filtered, args.output, args.format)
        else:
            print("class_name,class_number,title,language,subject,url")
            for record in filtered:
                print(
                    f"{record.get('class_name','')},{record.get('class_number','')},{record.get('title','')},{record.get('language','')},{record.get('subject','')},{record.get('url','')}"
                )

    if args.download and filtered:
        print(f"Found {len(filtered)} matching records for {args.url}")
        print(f"Starting download to {args.download_dir}...")
        saved_files = download_books(
            filtered,
            args.download_dir,
            max_workers=getattr(args, "download_workers", 1),
            delay_seconds=getattr(args, "download_delay", 3.0),
            insecure_ssl=getattr(args, "insecure_ssl", False),
        )
        print(f"Downloaded {len(saved_files)} files to {args.download_dir}")
    elif args.download:
        print(f"No matching records found for {args.url}; nothing to download.")