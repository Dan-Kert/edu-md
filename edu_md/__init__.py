from core.ance import AnceParser
from core.eduresurse import EduResurseParser
from core.config import CTICE_URL, EDURESURSE_URL
from core.ctice import (
    CticeParser,
    download_books,
    run,
    save_output,
)
from core.utils import (
    DEFAULT_HEADERS,
    detect_language,
    detect_subject,
    extract_class_number,
    normalize_class_name,
    roman_to_int,
)

__version__ = "0.1.0"

__all__ = [
    "CTICE_URL",
    "EDURESURSE_URL",
    "DEFAULT_HEADERS",
    "AnceParser",
    "CticeParser",
    "EduResurseParser",
    "detect_language",
    "detect_subject",
    "download_books",
    "extract_class_number",
    "normalize_class_name",
    "roman_to_int",
    "run",
    "save_output",
]