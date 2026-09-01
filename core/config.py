import warnings
from typing import List, Optional, Union
from .ance import AnceParser

CTICE_URL = "https://ctice.gov.md/?page_id=447"
ANCE_URL = "https://ance.gov.md/"
EDURESURSE_URL = "https://eduresurse.gov.md/ru/catalog"
discover_ance_session_urls = AnceParser.discover_ance_session_urls

SESSION_MAP = {
    "sb": "testb",
    "testb": "testb",
    "ss": "ss",
    "sr": "ss",
    "sesiune-suplimentara": "ss",
    "pret": "pret",
    "pretest": "pret",
    "pretestare": "pret",
    "exer": "exer",
    "exercitii": "exer",
    "exersare": "exer",
    "all": ["testb", "ss", "pret", "exer"],
}

SUBJECT_ALIASES = {
    "ctice": {
        "matematica": ["matematica", "math", "mat", "математика", "mate"],
        "fizica": ["fizica", "physics", "физика"],
        "chimie": ["chimie", "chemistry", "химия"],
        "biologie": ["biologie", "biology"],
        "geografie": ["geografie", "geography"],
        "istorie": ["istorie", "history", "история"],
        "informatica": ["informatica", "computer science", "it"],
        "limba engleza": ["engleza", "english", "limba engleza", "en"],
        "limba franceza": ["franceza", "french", "limba franceza", "fr"],
        "limba romana": ["limba romana", "romana", "romanian", "ro"],
        "limba rusa": ["limba rusa", "rusa", "russian", "ru"],
        "limba bulgara": ["limba bulgara", "bulgara", "bulgarian", "bg"],
        "limba gagauza": ["limba gagauza", "gagauza", "gagauz", "gag"],
        "limba ucraineana": ["limba ucraineana", "ucraineana", "ukrainian", "ukr", "ucr"],
        "literatura": ["literatura", "literature"],
    },
    "ance": {
        "matematica": ["mat", "math", "matematica", "математика"],
        "fizica": ["fiz", "fizica", "physics"],
        "chimie": ["chi", "chim", "chimie", "chemistry"],
        "biologie": ["bio", "biologie", "biology"],
        "geografie": ["geo", "geografie", "geography"],
        "istorie": ["ist", "istorie", "history", "история"],
        "informatica": ["inf", "informatica", "computer science"],
        "limba engleza": ["len", "en", "english", "engleza", "limba engleza"],
        "limba franceza": ["lfr", "limba franceza", "franceza", "french", "fr"],
        "limba romana": ["llro", "llroal", "limba romana", "romana", "romanian", "ro"],
        "limba rusa": ["llru", "limba rusa", "rusa", "russian", "ru"],
        "limba bulgara": ["llbg", "limba bulgara", "bulgara", "bulgarian", "bg"],
        "limba gagauza": ["llgag", "limba gagauza", "gagauza", "gagauz"],
        "limba ucraineana": ["llucr", "limba ucraineana", "ucraineana", "ukrainian", "ukr", "ucr"],
        "literatura": ["litt", "lit", "literatura", "literature"],
        "cultura": ["cult", "cultura"],
        "pregatire sportiva": ["prsp", "pregatire sportiva", "sport"],
        "istoria artei plastice": ["istartpl", "istoria artei plastice", "arta plastica"],
        "istoria artei teatrale": ["istartteatr", "istoria artei teatrale", "arta teatrala"],
        "istoria dansului bulgar": ["istdansbulg", "istoria dansului bulgar", "dansul bulgar"],
    },
}

def normalize_subject_key(value: str) -> str:
    if value is None:
        return ""
    return str(value).strip().lower().replace("_", " ").replace("-", " ")

def resolve_subject_alias(value: str, source: str = "ctice") -> Optional[str]:
    if value is None:
        return None
    token = normalize_subject_key(value)
    token = " ".join(token.split())
    aliases = SUBJECT_ALIASES.get(source, SUBJECT_ALIASES["ctice"]) if source else SUBJECT_ALIASES["ctice"]
    for canonical, items in aliases.items():
        for alias in items:
            if token == normalize_subject_key(alias):
                return canonical
    return None

def subject_aliases_for_source(value: str, source: str = "ctice") -> List[str]:
    canonical = resolve_subject_alias(value, source=source)
    if not canonical:
        return []
    aliases = SUBJECT_ALIASES.get(source, SUBJECT_ALIASES["ctice"]).get(canonical, [])
    return [normalize_subject_key(item) for item in aliases if item]

def build_ance_urls(years: List[int], session: str = "sb", class_number: int = 9) -> List[str]:
    if class_number not in {4, 9, 12}:
        raise ValueError("ANCE class_number must be one of 4, 9, 12")

    normalized_session = str(session or "sb").strip().lower().replace(" ", "-")
    normalized_session = normalized_session.replace("_", "-")
    if normalized_session in {"sr", "sesiune-suplimentara"}:
        normalized_session = "ss"
    elif normalized_session in {"pretest", "pretestare"}:
        normalized_session = "pret"
    elif normalized_session in {"exercitii", "exersare"}:
        normalized_session = "exer"

    session_codes: Union[str, List[str]] = SESSION_MAP.get(normalized_session, SESSION_MAP["sb"])
    if isinstance(session_codes, str):
        session_codes = [session_codes]

    discovered = discover_ance_session_urls(class_number)
    selected_years = sorted(set(years)) if years else sorted(discovered)
    missing_years = [year for year in selected_years if year not in discovered]
    for year in missing_years:
        warnings.warn(f"Year {year} not found in ANCE class {class_number} menu — skipped")

    urls: List[str] = []
    for year in selected_years:
        if year not in discovered:
            continue
        for base_url in discovered[year]:
            for code in session_codes:
                urls.append(f"{base_url}?field_categoriia_value={code}")
    return urls

__all__ = ["CTICE_URL", "ANCE_URL", "EDURESURSE_URL", "SESSION_MAP", "build_ance_urls"]