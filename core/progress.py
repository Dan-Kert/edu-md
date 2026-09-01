import sys
from typing import Optional

def format_download_progress(percent: int, title: str) -> str:
    width = 11
    filled = max(0, min(width, int(round((percent / 100) * width))))
    bar = "[" + ("#" * filled) + (" " * (width - filled)) + "]"
    label = title.strip() or "Downloading file"
    return f"download: {bar} {percent}% - {label}"

def format_crawl_progress(source: str, current: int, total: Optional[int] = None) -> str:
    if total:
        percent = min(100, int((current / total) * 100))
        width = 11
        filled = max(0, min(width, int(round((percent / 100) * width))))
        bar = "[" + ("#" * filled) + (" " * (width - filled)) + "]"
        return f"[{source}] crawl: {bar} {current}/{total}"
    else:
        return f"[{source}] crawl: ... {current} resources"

def print_progress_update(message: str, end: str = "\r", flush: bool = True) -> None:
    print(message, end=end, file=sys.stderr, flush=flush)

def print_phase_start(source: str, phase: str, url: Optional[str] = None) -> None:
    msg = f"[{source}] {phase}"
    if url:
        msg += f": {url}"
    print(msg, file=sys.stderr)

def print_phase_end(source: str, phase: str, count: int, duration_sec: Optional[float] = None) -> None:
    msg = f"[{source}] {phase} completed: {count} items"
    if duration_sec is not None:
        msg += f" ({duration_sec:.1f}s)"
    print(msg, file=sys.stderr)

def print_error(source: str, message: str) -> None:
    print(f"[{source}] ERROR: {message}", file=sys.stderr)

def print_warning(source: str, message: str) -> None:
    print(f"[{source}] WARNING: {message}", file=sys.stderr)

def complete_progress_line() -> None:
    print("", file=sys.stderr)