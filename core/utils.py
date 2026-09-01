import re
import time
from typing import Optional
import requests

REQUEST_DELAY_SECONDS = 2.5

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

LANGUAGE_ALIASES = {
    "ro": "romanian",
    "romanian": "romanian",
    "romana": "romanian",
    "limba romana": "romanian",
    "limba română": "romanian",
    "ru": "russian",
    "russian": "russian",
    "rusa": "russian",
    "limba rusa": "russian",
    "limba rusă": "russian",
    "рус": "russian",
    "русск": "russian",
    "русский": "russian",
    "en": "english",
    "english": "english",
    "engleza": "english",
    "limba engleza": "english",
    "fr": "french",
    "french": "french",
    "franceza": "french",
    "français": "french",
    "limba franceza": "french",
    "gag": "gagauz",
    "gagauz": "gagauz",
    "limba gagauza": "gagauz",
    "bg": "bulgarian",
    "bulgarian": "bulgarian",
    "bulgar": "bulgarian",
    "limba bulgara": "bulgarian",
    "болгар": "bulgarian",
    "болгарски": "bulgarian",
    "български": "bulgarian",
    "ucr": "ukrainian",
    "ukrainian": "ukrainian",
    "ukrain": "ukrainian",
    "ucrain": "ukrainian",
    "limba ucraineana": "ukrainian",
    "limba ucrainiană": "ukrainian",
    "укр": "ukrainian",
    "україн": "ukrainian",
    "українськ": "ukrainian",
    "українська": "ukrainian",
    "all": "all",
}

def polite_get(session, url: str, delay_seconds: Optional[float] = None, **kwargs):
    if delay_seconds is None:
        delay_seconds = REQUEST_DELAY_SECONDS

    response = None
    retries = 0
    retryable_statuses = {403, 429, 500, 502, 503, 504}

    while True:
        try:
            response = session.get(url, **kwargs)
            status_code = getattr(response, "status_code", None)
            if status_code in retryable_statuses:
                raise requests.exceptions.HTTPError(f"status {status_code}")
            if hasattr(response, "raise_for_status"):
                response.raise_for_status()
            if delay_seconds > 0:
                time.sleep(delay_seconds)
            return response
        except requests.exceptions.HTTPError:
            status_code = getattr(response, "status_code", None) if response is not None else None
            if status_code not in retryable_statuses:
                raise
            if retries >= 3:
                raise
            retry_after = getattr(getattr(response, "headers", None), "get", lambda *args, **kwargs: None)("Retry-After")
            delay = 1.0
            if retry_after:
                try:
                    delay = max(float(retry_after), 1.0)
                except ValueError:
                    delay = 1.0
            delay *= 2 ** retries
            time.sleep(delay)
            retries += 1
        except requests.exceptions.RequestException:
            if retries >= 3:
                raise
            time.sleep(min(1.5 * (2 ** retries), 12.0))
            retries += 1

def normalize_language_alias(value: str) -> Optional[str]:
    if value is None:
        return None
    token = str(value).strip().lower().replace("_", " ").replace("-", " ")
    token = re.sub(r"\s+", " ", token).strip()
    return LANGUAGE_ALIASES.get(token)

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
    if not text:
        return ""

    text = text.strip()
    match = re.match(r"^(?i:clasa)\s*(?:a\s*)?([ivxlcdm]+)\s*(?:-\s*a)?$", text)
    if match:
        numeral = match.group(1).upper()
        return f"Clasa a {numeral}-a"

    match = re.match(r"^(?i:clasa)\s*a\s*(.*)$", text)
    if match:
        rest = match.group(1).strip()
        if not rest:
            return "Clasa a"
        return f"Clasa a {rest}"

    match = re.match(r"^(?i:clasa)\s*(.*)$", text)
    if match:
        rest = match.group(1).strip()
        if rest:
            return f"Clasa a {rest}"
        return "Clasa a"

    return text

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
    letters = r"A-Za-zÀ-ÖØ-öø-ÿĂăÂâÎîȘșȚțА-Яа-яЁё"

    aliases = sorted(
        ((alias, canonical) for alias, canonical in LANGUAGE_ALIASES.items() if alias not in {"all"} and len(alias) > 2),
        key=lambda item: len(item[0]),
        reverse=True,
    )
    for alias, canonical in aliases:
        if alias in lower:
            return canonical

    short_aliases = [
        (alias, canonical)
        for alias, canonical in LANGUAGE_ALIASES.items()
        if alias not in {"all"} and len(alias) == 2
    ]
    for alias, canonical in short_aliases:
        pattern = rf"(?<![{letters}]){re.escape(alias)}(?![{letters}])"
        if re.search(pattern, lower):
            return canonical

    if "рус" in lower or "rusa" in lower:
        return "russian"
    if "україн" in lower or "укр" in lower or "мова" in lower:
        return "ukrainian"
    if "болгар" in lower or "български" in lower:
        return "bulgarian"
    if any(token in lower for token in ["romana", "română", "romanian", "limba"]):
        return "romanian"

    return "unknown"

def detect_subject(title: str) -> str:
    clean_title = re.sub(r"^\s*[IVXLCDM]+\s*[_ ]", "", title, flags=re.I).strip()
    lower = clean_title.lower()

    if "математ" in lower or "matemat" in lower:
        return "matematica"
    if "физик" in lower or "fizic" in lower:
        return "fizica"
    if "хими" in lower or "chimi" in lower:
        return "chimie"
    if "биолог" in lower or "biolog" in lower:
        return "biologie"
    if "географ" in lower or "geograf" in lower:
        return "geografie"
    if "истор" in lower or "istor" in lower:
        return "istorie"
    if "информ" in lower or "informat" in lower:
        return "informatica"
    if "музик" in lower or "muzic" in lower:
        return "educatie muzicala"
    if "пласт" in lower or "plastic" in lower:
        return "educatie plastica"
    if "технолог" in lower or "tehnologic" in lower:
        return "educatie tehnologica"
    if "абец" in lower or "abecedar" in lower:
        return "abecedar"
    if "literatura universala" in lower or "literatura universală" in lower or "література універсал" in lower:
        return "literatura universala"
    if "engleza" in lower or "english" in lower or "англ" in lower:
        return "limba engleza"
    if "franceza" in lower or "français" in lower or "франц" in lower:
        return "limba franceza"
    if "gagauz" in lower or "гагауз" in lower:
        return "limba gagauza"
    if "bulgar" in lower or "болгар" in lower or "българ" in lower:
        return "limba bulgara"
    if "ucrain" in lower or "ukrain" in lower or "україн" in lower or "укр" in lower:
        return "limba ucraineana"
    if "limba" in lower and "literatura" in lower:
        if "rusa" in lower or "рус" in lower or "руск" in lower or "russian" in lower:
            return "limba si literatura rusa"
        if "ucrainean" in lower or "україн" in lower or "укр" in lower or "мова" in lower:
            return "limba si literatura ucraineana"
        return "limba si literatura romana"
    if "мова" in lower and "література" in lower:
        if "рус" in lower or "руск" in lower:
            return "limba si literatura rusa"
        if "україн" in lower or "укр" in lower:
            return "limba si literatura ucraineana"
        return "limba si literatura romana"
    if "limba rusa" in lower or "rusa" in lower or "рус" in lower or "руск" in lower:
        return "limba rusa"
    if "мова" in lower and "рус" in lower:
        return "limba rusa"
    if "limba romana" in lower or "romana" in lower or "română" in lower:
        return "limba romana"

    return "other"