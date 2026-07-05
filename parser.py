import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

import requests
from bs4 import BeautifulSoup
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL = "https://ctice.gov.md/?page_id=447"
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://ctice.gov.md/",
}

ROMAN_VALUES = {
    "I": 1,
    "V": 5,
    "X": 10,
    "L": 50,
    "C": 100,
    "D": 500,
    "M": 1000,
}

def roman_to_int(value: str) -> Optional[int]:
    value = value.strip().upper()
    total = 0
    prev = 0
    for ch in reversed(value):
        current = ROMAN_VALUES.get(ch)
        if current is None:
            return None
        if current < prev:
            total -= current
        else:
            total += current
            prev = current
    return total

def normalize_class_name(raw: str) -> str:
    text = re.sub(r"\s+", " ", raw or "").strip()
    return text.replace("Clasa a", "Clasa a").strip()

def extract_class_number(class_name: str, title: str = "") -> Optional[int]:
    match = re.search(r"Clasa a\s*([IVXLCDM]+)", class_name, re.I)
    if match:
        return roman_to_int(match.group(1))

    match = re.match(r"^\s*([IVXLCDM]+)\s*[_ ].*", title, re.I)
    if match:
        return roman_to_int(match.group(1))

    return None


def detect_language(title: str) -> str:
    lower = title.lower()

    if any(token in lower for token in ["limba rusa", "limba rusă", "limba-rusa", "in rusa", "rusa)", "rusa.", "rusa "]):
        return "russian"

    if any(token in lower for token in ["limba romana", "limba română", "limba-romana", "in romana", "romana)", "lima romana", "lima româna", "romana "]):
        return "romanian"

    if any(token in lower for token in ["engleza", "english"]):
        return "english"
    if any(token in lower for token in ["franceza", "français", "french"]):
        return "french"
    if "gagauz" in lower:
        return "gagauz"
    if any(token in lower for token in ["bulgar", "bulgarian"]):
        return "bulgarian"
    if any(token in lower for token in ["ukrain", "ucrain", "ukrainian"]):
        return "ukrainian"

    if any(token in lower for token in ["рус", "rusa"]):
        return "russian"
    if any(token in lower for token in ["romana", "română", "romanian", "limba"]):
        return "romanian"

    return "unknown"

def detect_subject(title: str) -> str:
    clean_title = re.sub(r"^\s*[IVXLCDM]+\s*[_ ]", "", title, flags=re.I).strip()
    lower = clean_title.lower()

    if "matemat" in lower:
        return "matematica"
    if "fizic" in lower:
        return "fizica"
    if "chimi" in lower:
        return "chimie"
    if "biolog" in lower:
        return "biologie"
    if "geograf" in lower:
        return "geografie"
    if "istor" in lower:
        return "istorie"
    if "informat" in lower:
        return "informatica"
    if "muzic" in lower:
        return "educatie muzicala"
    if "plastic" in lower:
        return "educatie plastica"
    if "tehnologic" in lower:
        return "educatie tehnologica"
    if "abecedar" in lower:
        return "abecedar"
    if "literatura universala" in lower or "literatura universală" in lower:
        return "literatura universala"
    if "engleza" in lower or "english" in lower:
        return "limba engleza"
    if "franceza" in lower or "français" in lower:
        return "limba franceza"
    if "gagauz" in lower:
        return "limba gagauza"
    if "bulgar" in lower:
        return "limba bulgara"
    if "ucrain" in lower or "ukrain" in lower:
        return "limba ucraineana"
    if "limba" in lower and "literatura" in lower:
        if "rusa" in lower or "рус" in lower:
            return "limba si literatura rusa"
        return "limba si literatura romana"
    if "limba rusa" in lower or "rusa" in lower:
        return "limba rusa"
    if "limba romana" in lower or "romana" in lower or "română" in lower:
        return "limba romana"

    return "other"

class CticeParser:
    def __init__(self, url: str = BASE_URL) -> None:
        self.url = url

    def fetch_html(self) -> str:
        response = requests.get(self.url, headers=DEFAULT_HEADERS, timeout=30)
        response.raise_for_status()
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

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Parse CTICE textbooks from the public manual page")
    parser.add_argument("--url", default=BASE_URL, help="Web page that contains the manuals")
    parser.add_argument("--classes", default=None, help="Comma-separated class numbers, for example 5,6,7,8")
    parser.add_argument("--grade-range", default=None, help="Inclusive range such as 5:8")
    parser.add_argument("--keywords", default=None, help="Comma-separated keywords, for example 'limba si literatura romana,matematica'")
    parser.add_argument("--languages", default=None, help="Comma-separated languages: romanian,russian")
    parser.add_argument("--format", choices=["json", "csv"], default="json", help="Output format")
    parser.add_argument("--output", default=None, help="Path to write the result")
    parser.add_argument("--download", action="store_true", help="Download matching PDF files")
    parser.add_argument("--download-dir", default="./downloads", help="Directory for downloaded manuals")
    return parser.parse_args()

def parse_classes_arg(value: Optional[str]) -> List[int]:
    if not value:
        return []
    classes: List[int] = []
    for item in value.split(","):
        item = item.strip()
        if not item:
            continue
        if ":" in item:
            start_raw, end_raw = item.split(":", 1)
            start, end = int(start_raw), int(end_raw)
            classes.extend(range(start, end + 1))
        else:
            classes.append(int(item))
    return sorted(set(classes))


def parse_grade_range(value: Optional[str]) -> List[int]:
    if not value:
        return []
    start_raw, end_raw = value.split(":", 1)
    return list(range(int(start_raw), int(end_raw) + 1))


def parse_keywords_arg(value: Optional[str]) -> List[str]:
    if not value:
        return []
    return [token.strip() for token in value.split(",") if token.strip()]


def parse_languages_arg(value: Optional[str]) -> List[str]:
    if not value:
        return []
    return [token.strip().lower() for token in value.split(",") if token.strip()]


def save_output(records: Sequence[Dict[str, Any]], output_path: Optional[str], output_format: str) -> None:
    if not output_path:
        return
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if output_format == "json":
        path.write_text(json.dumps(list(records), ensure_ascii=False, indent=2), encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["class_name", "class_number", "title", "language", "subject", "url", "filename"])
        writer.writeheader()
        for record in records:
            writer.writerow(record)


def download_books(records: Sequence[Dict[str, Any]], download_dir: str) -> List[Path]:
    download_path = Path(download_dir)
    download_path.mkdir(parents=True, exist_ok=True)
    saved: List[Path] = []
    for record in records:
        url = record.get("url", "")
        if not url:
            continue
        filename = record.get("filename") or Path(url).name or f"{record.get('class_number', 'manual')}.pdf"
        safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", filename)[:180]
        target = download_path / safe_name
        try:
            print(f"Downloading: {filename}...")
            response = requests.get(url, headers=DEFAULT_HEADERS, timeout=60, verify=False)
            response.raise_for_status()
            target.write_bytes(response.content)
            saved.append(target)
        except Exception as e:
            print(f"Error downloading {filename}: {e}")
    return saved

def main() -> None:
    args = parse_args()
    parser = CticeParser(url=args.url)
    books = parser.fetch_books()

    classes = parse_classes_arg(args.classes)
    if args.grade_range:
        classes.extend(parse_grade_range(args.grade_range))
    classes = sorted(set(classes))

    keywords = parse_keywords_arg(args.keywords)
    languages = parse_languages_arg(args.languages)
    filtered = parser.filter_books(books, classes=classes, keywords=keywords, languages=languages)

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
        saved_files = download_books(filtered, args.download_dir)
        print(f"Downloaded {len(saved_files)} files to {args.download_dir}")

if __name__ == "__main__":
    main()
