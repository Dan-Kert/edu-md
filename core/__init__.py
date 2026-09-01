from .ance import AnceParser
from .eduresurse import EduResurseParser
from .config import CTICE_URL, EDURESURSE_URL
from .ctice import (
    CticeParser,
    download_books,
    run,
    save_output,
)
from .utils import (
    DEFAULT_HEADERS,
    detect_language,
    detect_subject,
    extract_class_number,
    normalize_class_name,
    roman_to_int,
)

BASE_URL = CTICE_URL

__all__ = [
    "BASE_URL",
    "DEFAULT_HEADERS",
    "AnceParser",
    "CticeParser",
    "EduResurseParser",
    "EDURESURSE_URL",
    "detect_language",
    "detect_subject",
    "download_books",
    "extract_class_number",
    "normalize_class_name",
    "roman_to_int",
    "run",
    "save_output",
]