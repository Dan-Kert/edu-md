import argparse
import copy
import json
import os
import re
import sys
from pathlib import Path
from typing import Iterable, List, Optional, Set, Tuple
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from core.ctice import run
from core.config import CTICE_URL, ANCE_URL, EDURESURSE_URL, build_ance_urls, resolve_subject_alias, subject_aliases_for_source
from core.utils import normalize_language_alias

def add_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--classes", default=None, help="Comma-separated class numbers or ranges, e.g. 5,6,7 or 5:8 or 5-8")
    parser.add_argument("--search", dest="search", default=None, help="Search by text and subject aliases. Value is matched as a substring across title, subject, class, URL, and filename.")
    parser.add_argument("--languages", default=None, help="Comma-separated languages: ro, ru, en, fr, gagauz, bulgarian, ukranian")
    parser.add_argument("--output", default="./downloads/edu_md_results.json", help="Path to write the result. Default: ./downloads/edu_md_results.json")
    parser.set_defaults(download=True, format="json", download_dir="./downloads")
    parser.add_argument("--all", action="store_true", help="Download all available resources across the selected source(s); if used alone, it covers CTICE, ANCE and EduResurse.")
    parser.add_argument("--info", dest="download", action="store_false", help="Only fetch metadata and skip downloading files.")
    parser.add_argument("--download-workers", type=int, default=1, help="Number of parallel download workers (default: 1)")
    parser.add_argument("--download-delay", type=float, default=3.0, help="Pause in seconds between downloads (default: 3.0)")
    parser.add_argument("--interactive", action="store_true", help="Launch interactive source selection menu")
    parser.add_argument("--insecure-ssl", action="store_true", help="Allow fallback to unverified SSL certificates if verification fails (use with caution)")

def add_ctice_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--ctice-url", default=None, help="URL of CTICE page to parse (example: default CTICE manuals page)")
    parser.add_argument("--ctice", "--books", action="store_true", dest="ctice", help="Shortcut: parse CTICE manuals")

def add_ance_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--ance-url", default=None, help="URL of ANCE session page to parse (example: class/session page)")
    parser.add_argument("--ance", "--tests", action="store_true", dest="ance", help="Shortcut: parse ANCE tests")
    parser.add_argument("--years", default=None, help="Comma-separated years or range, e.g. 2023,2024 or 2023-2025")
    parser.add_argument("--session", choices=["sb", "ss", "pret", "exer"], default="sb", help="ANCE session type: sb (Sesiunea de bază), ss (Sesiune suplimentară), pret (Pretestare), or exer (Teste pentru exersare)")
    parser.add_argument("--kind", choices=["test", "barem"], default=None, help="Select ANCE document kind: test or barem")

def add_eduresurse_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--eduresurse-url", default=None, help="URL of EduResurse catalog/resource page to parse")
    parser.add_argument("--eduresurse", "--resources", action="store_true", dest="eduresurse", help="Shortcut: parse EduResurse resources")
    parser.add_argument("--resource-types", default=None, help="Comma-separated resource types for EduResurse: video, audio, pdf, doc, archive, image, html, other")
    parser.add_argument("--education-category-id", default=None, help="EduResurse education_category_id filter, e.g. 1, 2")
    parser.add_argument("--degree-id", default=None, help="EduResurse degree_id filter, e.g. 1, 2")
    parser.add_argument("--discipline-id", default=None, help="EduResurse discipline_id filter, e.g. 37, 42")
    parser.add_argument("--catalog-type", default=None, help="EduResurse catalog type query parameter, e.g. pdf_textbook, video, doc")

def build_eduresurse_url(
    base_url: Optional[str],
    education_category_id: Optional[str] = None,
    degree_id: Optional[str] = None,
    discipline_id: Optional[str] = None,
    catalog_type: Optional[str] = None,
) -> Optional[str]:
    if not base_url:
        return None
    parsed = urlsplit(base_url)
    if not parsed.scheme:
        return base_url

    params = dict(parse_qsl(parsed.query, keep_blank_values=True))
    if education_category_id is not None and str(education_category_id).strip():
        params["education_category_id"] = str(education_category_id).strip()
    if degree_id is not None and str(degree_id).strip():
        params["degree_id"] = str(degree_id).strip()
    if discipline_id is not None and str(discipline_id).strip():
        params["discipline_id"] = str(discipline_id).strip()
    if catalog_type is not None and str(catalog_type).strip():
        params["type"] = str(catalog_type).strip()

    path = parsed.path or "/ru/catalog"
    return urlunsplit((parsed.scheme, parsed.netloc, path, urlencode(params), parsed.fragment))

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Parse CTICE manuals, ANCE tests and EduResurse resources from public pages", allow_abbrev=False)
    parser.set_defaults(all=False)

    add_ctice_arguments(parser)
    add_ance_arguments(parser)
    add_eduresurse_arguments(parser)
    add_common_arguments(parser)

    return parser.parse_args()

def prompt_input(prompt: str, default: Optional[str] = None) -> str:
    answer = input(f"{prompt}{' [' + default + ']' if default else ''}: ").strip()
    if not answer and default is not None:
        return default
    return answer

def prompt_choice(prompt: str, options: dict, default: Optional[str] = None) -> str:
    print(prompt)
    for key, description in options.items():
        print(f"  {key}) {description}")
    while True:
        choice = input(f"Select option{f' [{default}]' if default else ''}: ").strip()
        if not choice and default is not None:
            return default
        if choice in options:
            return choice
        print("Invalid choice, please try again.")

def interactive_menu() -> argparse.Namespace:
    print("\n=== Interactive Setup ===")
    source = prompt_choice(
        "Choose platform:",
        {"1": "CTICE manuals", "2": "ANCE tests", "3": "EduResurse resources", "4": "Both CTICE and ANCE"},
        default="1",
    )

    args = argparse.Namespace(
        ctice_url=None,
        ance_url=None,
        eduresurse_url=None,
        all=False,
        ctice=False,
        ance=False,
        eduresurse=False,
        classes=None,
        years=None,
        session="sb",
        search=None,
        keywords=None,
        subjects=None,
        languages=None,
        resource_types=None,
        education_category_id=None,
        degree_id=None,
        discipline_id=None,
        catalog_type=None,
        kind=None,
        format="json",
        output="./downloads/edu_md_results.json",
        download=True,
        download_dir="./downloads",
        download_workers=1,
        download_delay=3.0,
        interactive=True,
        url=None,
    )

    if source == "1":
        args.ctice = True
    elif source == "2":
        args.ance = True
    elif source == "3":
        args.eduresurse = True
    else:
        args.all = True

    if args.ctice:
        use_default = prompt_choice(
            "Use default CTICE URL?", {"1": "Yes", "2": "No"}, default="1"
        )
        if use_default == "1":
            args.ctice_url = CTICE_URL
        else:
            args.ctice_url = prompt_input("Enter CTICE URL", CTICE_URL)

    if args.ance:
        use_default = prompt_choice(
            "Use default ANCE URL?", {"1": "Yes", "2": "No"}, default="1"
        )
        if use_default == "1":
            args.ance_url = ANCE_URL
        else:
            args.ance_url = prompt_input("Enter ANCE URL", ANCE_URL)

    if args.eduresurse:
        use_default = prompt_choice(
            "Use default EduResurse URL?", {"1": "Yes", "2": "No"}, default="1"
        )
        if use_default == "1":
            args.eduresurse_url = EDURESURSE_URL
        else:
            args.eduresurse_url = prompt_input("Enter EduResurse URL", EDURESURSE_URL)

    if args.all:
        args.ctice_url = prompt_input("Enter CTICE URL", CTICE_URL)
        args.ance_url = prompt_input("Enter ANCE URL", ANCE_URL)

    args.classes = prompt_input("Enter classes to filter (comma/range, e.g. 5,6,7 or 5-8)", "") or None
    args.search = prompt_input("Enter search text or subject alias (comma-separated)", "") or None
    args.keywords = args.search
    args.subjects = args.search

    if args.ance or args.all:
        args.years = prompt_input("Enter ANCE years (comma/range, e.g. 2022,2023 or 2022-2025)", "") or None
        args.session = prompt_choice(
            "Choose ANCE session:",
            {"sb": "Sesiunea de bază", "ss": "Sesiune suplimentară", "pret": "Pretestare", "exer": "Teste pentru exersare"},
            default="sb",
        )
        args.kind = prompt_choice(
            "Choose ANCE kind:",
            {"test": "Tests only", "barem": "Answer keys only"},
            default="test",
        )

    if args.ctice or args.ance or args.eduresurse or args.all:
        args.languages = prompt_input("Enter languages (ro, ru, en, fr, etc.)", "") or None
        if args.eduresurse or args.all:
            args.resource_types = prompt_input("Enter EduResurse resource types (video,pdf,doc,audio,image,archive,html,other)", "") or None
    else:
        args.years = None

    args.format = "json"
    args.output = prompt_input("Enter output file path (leave blank to use ./downloads/edu_md_results.json)", "./downloads/edu_md_results.json")
    if not args.output:
        args.output = "./downloads/edu_md_results.json"
    download_answer = prompt_choice(
        "Download matching files?", {"1": "Yes", "2": "No"}, default="2"
    )
    args.download = download_answer == "1"
    args.download_workers = int(prompt_input("Enter parallel download workers", str(args.download_workers)) or args.download_workers)
    args.download_delay = float(prompt_input("Enter pause between downloads in seconds", str(args.download_delay)) or args.download_delay)
    return args

def parse_classes_arg(value: Optional[str]) -> List[int]:
    if not value:
        return []
    classes: List[int] = []
    for item in value.split(","):
        item = item.strip()
        if not item:
            continue
        try:
            if ":" in item or "-" in item:
                sep = ":" if ":" in item else "-"
                start_raw, end_raw = item.split(sep, 1)
                start, end = int(start_raw.strip()), int(end_raw.strip())
                if start <= end:
                    classes.extend(range(start, end + 1))
                else:
                    classes.extend(range(end, start + 1))
            else:
                classes.append(int(item))
        except ValueError:
            # ignore invalid tokens, but continue parsing other items
            print(f"Warning: ignoring invalid class token '{item}'", )
            continue
    return sorted(set(classes))

def parse_keywords_arg(value: Optional[str]) -> List[str]:
    if not value:
        return []
    return [token.strip() for token in value.split(",") if token.strip()]

def parse_years_arg(value: Optional[str]) -> List[int]:
    if not value:
        return []
    years: List[int] = []
    normalized = value.replace("-", ":")
    for item in normalized.split(","):
        item = item.strip()
        if not item:
            continue
        if ":" in item:
            start_raw, end_raw = item.split(":", 1)
            try:
                start, end = int(start_raw.strip()), int(end_raw.strip())
                if start <= end:
                    years.extend(range(start, end + 1))
                else:
                    years.extend(range(end, start + 1))
            except ValueError:
                print(f"Warning: invalid year range '{item}'")
                continue
        else:
            try:
                years.append(int(item))
            except ValueError:
                print(f"Warning: invalid year '{item}'")
                continue
    return sorted(set(years))

def parse_languages_arg(value: Optional[str]) -> List[str]:
    if not value:
        return []
    tokens = [token.strip() for token in value.split(",") if token.strip()]
    if not tokens:
        return []

    normalized_languages: List[str] = []
    for token in tokens:
        canonical = normalize_language_alias(token)
        if canonical == "all":
            return ["all"]
        if canonical:
            normalized_languages.append(canonical)
        else:
            print(f"Warning: ignoring invalid language token '{token}'")
    return sorted(set(normalized_languages))

def parse_resource_types_arg(value: Optional[str]) -> List[str]:
    if not value:
        return []
    tokens = [token.strip().lower() for token in str(value).split(",") if token.strip()]
    if not tokens:
        return []
    valid = {"video", "audio", "pdf", "doc", "archive", "image", "html", "other", "download"}
    normalized: List[str] = []
    for token in tokens:
        if token in valid:
            normalized.append(token)
        else:
            print(f"Warning: ignoring invalid resource type '{token}'")
    return sorted(set(normalized))

def parse_subjects_arg(value: Optional[str], source: str = "ctice") -> List[str]:
    if not value:
        return []
    tokens = [token.strip() for token in value.split(",") if token.strip()]
    if not tokens:
        return []

    normalized_subjects: List[str] = []
    for token in tokens:
        canonical = resolve_subject_alias(token, source=source)
        if canonical:
            normalized_subjects.append(canonical)
        else:
            print(f"Warning: ignoring invalid subject token '{token}'")
    return sorted(set(normalized_subjects))

def validate_ance_classes(classes: Optional[List[int]]) -> None:
    if not classes:
        return
    if any(class_number not in {4, 9, 12} for class_number in classes):
        print("Warning: ANCE supports only classes 4, 9, 12 — other values will not produce results")

def main() -> None:
    args = parse_args()
    if not getattr(args, "output", None):
        args.output = "./downloads/edu_md_results.json"
    if not getattr(args, "download_dir", None):
        args.download_dir = "./downloads"
    if args.interactive or not (args.ctice_url or args.ance_url or getattr(args, 'eduresurse_url', None) or getattr(args, 'ctice', False) or getattr(args, 'ance', False) or getattr(args, 'eduresurse', False) or getattr(args, 'all', False)):
        args = interactive_menu()
    if not getattr(args, "output", None):
        args.output = "./downloads/edu_md_results.json"
    if not getattr(args, "download_dir", None):
        args.download_dir = "./downloads"

    if getattr(args, 'all', False):
        if not (args.ctice or args.ance or args.eduresurse):
            args.ctice = True
            args.ance = True
            args.eduresurse = True
        if getattr(args, 'ctice', False) and not args.ctice_url:
            args.ctice_url = CTICE_URL
        if getattr(args, 'ance', False) and not args.ance_url:
            args.ance_url = ANCE_URL
        if getattr(args, 'eduresurse', False) and not args.eduresurse_url:
            args.eduresurse_url = EDURESURSE_URL

    if not (args.ctice_url or args.ance_url or getattr(args, 'eduresurse_url', None) or getattr(args, 'ctice', False) or getattr(args, 'ance', False) or getattr(args, 'eduresurse', False) or getattr(args, 'all', False)):
        parser = argparse.ArgumentParser()
        parser.error("One of --ctice-url, --ance-url, --eduresurse-url, --ctice, --ance, --eduresurse, or --all must be provided")

    if getattr(args, 'ctice', False) and not args.ctice_url:
        args.ctice_url = CTICE_URL
    if getattr(args, 'ance', False) and not args.ance_url:
        args.ance_url = ANCE_URL
    if getattr(args, 'eduresurse', False) and not args.eduresurse_url:
        args.eduresurse_url = EDURESURSE_URL

    if getattr(args, 'eduresurse_url', None):
        args.eduresurse_url = build_eduresurse_url(
            args.eduresurse_url,
            getattr(args, 'education_category_id', None),
            getattr(args, 'degree_id', None),
            getattr(args, 'discipline_id', None),
            getattr(args, 'catalog_type', None),
        )

    selected_ctice = bool(args.ctice_url)
    selected_ance = bool(args.ance_url)
    if selected_ctice and selected_ance:
        args.all = True
    else:
        args.all = getattr(args, 'all', False)

    user_classes = parse_classes_arg(args.classes)
    user_classes = sorted(set(user_classes))
    classes_explicitly_set = bool(user_classes)
    years = parse_years_arg(args.years) if hasattr(args, 'years') else []
    search_tokens = parse_keywords_arg(getattr(args, 'search', None) or getattr(args, 'keywords', None))
    if not search_tokens:
        search_tokens = parse_keywords_arg(getattr(args, 'subjects', None))
    keywords = search_tokens
    languages = parse_languages_arg(args.languages)
    resource_types = parse_resource_types_arg(getattr(args, 'resource_types', None))
    args.resource_types = resource_types

    if args.download and not (classes_explicitly_set or search_tokens or languages or getattr(args, 'all', False)):
        sys.exit("Error: download requires at least one filter (--classes, --search, or --languages) to avoid downloading everything.")

    if args.all:
        base_output = args.output
        outputs = {}
        if base_output:
            p = Path(base_output)
            if p.exists() and p.is_dir() or str(base_output).endswith(os.path.sep) or str(base_output).endswith('/'):
                outputs['ctice'] = str(p / 'ctice_results.json')
                outputs['ance'] = str(p / 'ance_results.json')
                outputs['eduresurse'] = str(p / 'eduresurse_results.json')
            else:
                stem = p.stem
                ext = p.suffix or '.json'
                parent = p.parent or Path('.')
                outputs['ctice'] = str(parent / f'{stem}_ctice{ext}')
                outputs['ance'] = str(parent / f'{stem}_ance{ext}')
                outputs['eduresurse'] = str(parent / f'{stem}_eduresurse{ext}')
        else:
            outputs['ctice'] = '/tmp/ctice_results.json'
            outputs['ance'] = '/tmp/ance_results.json'
            outputs['eduresurse'] = '/tmp/eduresurse_results.json'

        selected_sources = []
        if getattr(args, 'ctice', False) or (not args.ance and not args.eduresurse and not args.ctice_url and not args.ance_url and not getattr(args, 'eduresurse_url', None)):
            selected_sources.append(('ctice', args.ctice_url or CTICE_URL))
        if getattr(args, 'ance', False) or (not args.ctice and not args.eduresurse and not args.ctice_url and not args.ance_url and not getattr(args, 'eduresurse_url', None)):
            selected_sources.append(('ance', args.ance_url or ANCE_URL))
        if getattr(args, 'eduresurse', False) or (not args.ctice and not args.ance and not args.ctice_url and not args.ance_url and not getattr(args, 'eduresurse_url', None)):
            selected_sources.append(('eduresurse', args.eduresurse_url or EDURESURSE_URL))
        if not selected_sources:
            selected_sources = []
            if args.ctice_url:
                selected_sources.append(('ctice', args.ctice_url))
            if args.ance_url:
                selected_sources.append(('ance', args.ance_url))
            if getattr(args, 'eduresurse_url', None):
                selected_sources.append(('eduresurse', args.eduresurse_url))

        for key, url in selected_sources:
            args_copy = copy.deepcopy(args)
            args_copy.output = outputs.get(key)
            args_copy.url = url
            args_copy.ctice = key == 'ctice'
            args_copy.ance = key == 'ance'
            args_copy.eduresurse = key == 'eduresurse'
            
            # Determine classes for this source
            if key == 'ance':
                source_classes = user_classes if user_classes else [4, 9, 12]
                validate_ance_classes(source_classes)
            else:
                source_classes = user_classes
            
            # Resolve subjects for this source
            # CTICE/ANCE use their own mappings; EduResurse falls back to CTICE
            # (because EduResurse has no subject filter at API level - filtering is local)
            source_for_subjects = key if key in {'ctice', 'ance'} else 'ctice'
            source_subjects = parse_subjects_arg(
                getattr(args, 'search', None) or getattr(args, 'subjects', None),
                source=source_for_subjects
            )
            
            try:
                run(args_copy, classes=source_classes, keywords=keywords, subjects=source_subjects, languages=languages, kind=args.kind)
            except Exception as e:
                print(f"Warning: skipped {url} due to error: {e}")
                continue
        return

    if args.eduresurse_url:
        args.url = args.eduresurse_url
        # EduResurse: subject filtering is done locally via detect_subject() after download
        # (no subject filter at API level). Use CTICE aliases as fallback for keyword matching.
        source_subjects = parse_subjects_arg(
            getattr(args, 'search', None) or getattr(args, 'subjects', None),
            source='ctice'
        )
        run(args, classes=user_classes, keywords=keywords, subjects=source_subjects, languages=languages, kind=args.kind)
        return

    if args.ctice_url:
        args.url = args.ctice_url
        source_subjects = parse_subjects_arg(
            getattr(args, 'search', None) or getattr(args, 'subjects', None),
            source='ctice'
        )
        run(args, classes=user_classes, keywords=keywords, subjects=source_subjects, languages=languages, kind=args.kind)
        return

    if args.ance_url:
        ance_classes = user_classes if user_classes else [4, 9, 12]
        validate_ance_classes(ance_classes)
        if args.ance_url == ANCE_URL:
            urls: List[str] = []
            for class_number in ance_classes:
                if class_number not in {4, 9, 12}:
                    continue
                urls.extend(build_ance_urls(years or [], session=args.session, class_number=class_number))
            if urls:
                for idx, u in enumerate(urls):
                    args_copy = copy.deepcopy(args)
                    args_copy.url = u
                    if args.output:
                        p = Path(args.output)
                        stem = p.stem
                        ext = p.suffix or '.json'
                        parent = p.parent or Path('.')
                        year = None
                        m = re.search(r"sesiunea-(\d{4})", u)
                        if m:
                            year = m.group(1)
                        label = year or str(idx + 1)
                        args_copy.output = str(parent / f"{stem}_ance_{label}{ext}")
                    
                    source_subjects = parse_subjects_arg(
                        getattr(args, 'search', None) or getattr(args, 'subjects', None),
                        source='ance'
                    )
                    
                    try:
                        run(args_copy, classes=ance_classes, keywords=keywords, subjects=source_subjects, languages=languages, kind=args.kind)
                    except Exception as e:
                        print(f"Warning: skipped {u} due to error: {e}")
                        continue
                return
        
        source_subjects = parse_subjects_arg(
            getattr(args, 'search', None) or getattr(args, 'subjects', None),
            source='ance'
        )
        args.url = args.ance_url
        run(args, classes=ance_classes, keywords=keywords, subjects=source_subjects, languages=languages, kind=args.kind)
        return

if __name__ == "__main__":
    main()