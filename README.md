# EDU-MD: Educational Resources Parser for Moldova

A Python toolkit for parsing and downloading educational materials from Moldovan educational platforms: **CTICE** (Curriculum manuals), **ANCE** (National examinations tests), and **EduResurse** (Educational resources catalog).

## Table of Contents

- [Features](#features)
- [Installation](#installation)
- [Python API (Library Usage)](#python-api-library-usage)
- [Command-Line Interface](#command-line-interface)
- [Parameters & Tags](#parameters--tags)
- [Subject Aliases](#subject-aliases)
- [Output Templates](#output-templates)
- [Examples](#examples)
- [Advanced Usage](#advanced-usage)

---

## Features

- ✅ **CTICE**: Download curriculum manuals by class and subject
- ✅ **ANCE**: Parse national examination tests (4 sessions: basic, supplementary, pretest, practice)
- ✅ **EduResurse**: Search educational resources with filters (type, category, discipline)
- ✅ **Flexible Filtering**: By class/year, subject, language, resource type
- ✅ **Batch Download**: Parallel downloads with configurable workers and delays
- ✅ **Output Format**: JSON only
- ✅ **Interactive Mode**: Menu-driven setup without command line arguments

---

## Installation

### Via pip (from source)

```bash
pip install -e .
```

### Via command line

```bash
edu-md [options]
```

---

## Python API (Library Usage)

You can use `edu-md` as a Python library in your own projects to parse educational materials programmatically.

### Basic Usage

#### CTICE Parser

```python
from core.ctice import CticeParser

# Create a parser instance
parser = CticeParser()

# Fetch and parse books
books = parser.fetch_books()

# Filter books by class and subject
filtered = parser.filter_books(
    books,
    classes=[9],
    keywords=["matematica"],
    languages=["romanian"]
)

# Print results
for book in filtered:
    print(f"{book['title']} - {book['subject']}")
```

#### ANCE Parser (Tests)

```python
from core.ance import AnceParser

# Create parser for a specific session URL
parser = AnceParser(url="https://ance.gov.md/clasa-sesiunea-examen/clasa-9")

# Fetch all tests from that URL and nested pages
tests = parser.fetch_tests()

# Print metadata
for test in tests:
    print(f"{test['title']} - Class {test['class_number']}")
```

#### EduResurse Parser (Resources)

```python
from core.eduresurse import EduResurseParser

# Create a parser for a catalog URL
parser = EduResurseParser(url="https://eduresurse.gov.md/ru/catalog")

# Fetch resources
resources = parser.fetch_resources()

# Filter by keyword and resource type
filtered = parser.filter_resources(
    resources,
    keywords=["matematica"],
    resource_types=["pdf"]
)

for resource in filtered:
    print(f"{resource['title']} ({resource['resource_type']})")
```

### Download Books Programmatically

```python
from core.ctice import CticeParser, download_books

# Get books
parser = CticeParser()
books = parser.fetch_books()
filtered = parser.filter_books(books, classes=[9])

# Download them
downloaded = download_books(
    filtered,
    download_dir="./my_books",
    max_workers=3,
    delay_seconds=2.0,
    insecure_ssl=False
)

print(f"Downloaded {len(downloaded)} files")
```

### Advanced: Custom Subject Aliases

```python
from core.config import resolve_subject_alias, SUBJECT_ALIASES

# Get canonical subject name
subject = resolve_subject_alias("math", source="ctice")
print(subject)  # Output: matematica

# Add custom aliases
SUBJECT_ALIASES["ctice"]["matematica"].append("mat_custom")

# Use updated aliases
new_subject = resolve_subject_alias("mat_custom", source="ctice")
print(new_subject)  # Output: matematica
```

### Available Classes

**Core Parsers:**
- `CticeParser(url, request_delay)` - Parse curriculum manuals
  - `fetch_books()` → `List[Dict]`
  - `parse_html(html)` → `List[Dict]`
  - `filter_books(books, classes, keywords, languages)` → `List[Dict]`

- `AnceParser(url, session, request_delay)` - Parse ANCE tests
  - `fetch_tests(visited, progress_counter)` → `List[Dict]`
  - `parse_html(html)` → `List[Dict]`
  - `parse_ance_filename(filename)` → `Optional[Dict]`
  - `discover_ance_session_urls(class_number)` → `Dict[int, List[str]]` (static)

- `EduResurseParser(url, request_delay)` - Parse EduResurse resources
  - `fetch_resources()` → `List[Dict]`
  - `filter_resources(records, classes, keywords, languages, resource_types)` → `List[Dict]`

**Utility Functions:**
- `save_output(records, output_path, output_format)` - Save to JSON
- `download_books(records, download_dir, max_workers, delay_seconds, insecure_ssl)` - Batch download
- `detect_language(text)` - Detect language from text
- `detect_subject(text)` - Detect subject from text
- `resolve_subject_alias(value, source)` - Resolve subject aliases

---

## Command-Line Interface

### Basic Syntax

```bash
edu-md [COMMON_OPTIONS] [SOURCE_OPTIONS] [FILTERS]
```

### Example

```bash
edu-md --ctice --classes 9 --search matematica
```

---

## Parameters & Tags

### Common Options

These options work with all sources (CTICE, ANCE, EduResurse).

**Default behavior**: Files are automatically downloaded. Use `--info` flag to fetch only metadata instead.

| Tag | Description | Type | Default | Example |
|-----|-------------|------|---------|---------|
| `--classes` | Filter by class numbers or ranges. Supports comma-separated values (5,6,7) or ranges (5:8, 5-8) | string (list/range) | None | `--classes 9` or `--classes 5,6,7` or `--classes 5:9` |
| `--search` | Free-text search and subject aliases. Matched as substring across title, subject, class, URL, filename | string | None | `--search matematica` or `--search math` |
| `--languages` | Filter by language codes: ro (Romanian), ru (Russian), en (English), fr (French), gagauz, bulgarian, ukrainian | string | None | `--languages ro,en` |
| `--output` | Path to output results file (JSON format) | string | `./downloads/edu_md_results.json` | `--output results.json` |
| `--info` | Fetch metadata only, skip downloading files | boolean flag | false | `--info` |
| `--download-workers` | Number of parallel download workers | integer | 1 | `--download-workers 4` |
| `--download-delay` | Pause in seconds between downloads (rate limiting) | float | 3.0 | `--download-delay 2.5` |
| `--all` | Download all available resources across all sources or all resources from selected source | boolean flag | false | `--all` |
| `--interactive` | Launch interactive menu for setup | boolean flag | false | `--interactive` |
| `--insecure-ssl` | Allow fallback to unverified SSL certificates if verification fails (use with caution) | boolean flag | false | `--insecure-ssl` |

### CTICE Options

Parse Romanian curriculum manuals from CTICE.

| Tag | Description | Type | Default | Example |
|-----|-------------|------|---------|---------|
| `--ctice, --books` | Enable CTICE source (uses default CTICE URL) | boolean flag | false | `--ctice` |
| `--ctice-url` | Custom CTICE page URL to parse | string | None | `--ctice-url "https://ctice.gov.md/?page_id=447"` |

**Default CTICE URL**: `https://ctice.gov.md/?page_id=447`

### ANCE Options

Parse national examination tests from ANCE. Supports classes 4, 9, and 12 only.

| Tag | Description | Type | Default | Example |
|-----|-------------|------|---------|---------|
| `--ance, --tests` | Enable ANCE source (uses default ANCE URL) | boolean flag | false | `--ance` |
| `--ance-url` | Custom ANCE session URL to parse | string | None | `--ance-url "https://ance.gov.md/..."` |
| `--years` | Comma-separated years or range: 2023,2024 or 2023-2025 | string | None | `--years 2023,2024` or `--years 2023-2025` |
| `--session` | ANCE session type to download | choice: sb, ss, pret, exer | `sb` | `--session ss` |
| `--kind` | Document type within session: test (exam papers) or barem (answer keys) | choice: test, barem | None | `--kind test` |

**Session Types**:
- `sb` = Sesiunea de bază (Basic/Standard Session)
- `ss` = Sesiune suplimentară (Supplementary Session)
- `pret` = Pretestare (Pretest/Mock Exam)
- `exer` = Teste pentru exersare (Practice Tests)

**Default ANCE URL**: `https://ance.gov.md/`

**Supported Classes**: 4, 9, 12

### EduResurse Options

Parse educational resources from EduResurse catalog. Supports multiple filter types.

| Tag | Description | Type | Default | Example |
|-----|-------------|------|---------|---------|
| `--eduresurse, --resources` | Enable EduResurse source (uses default EduResurse URL) | boolean flag | false | `--eduresurse` |
| `--eduresurse-url` | Custom EduResurse catalog or resource URL | string | None | `--eduresurse-url "https://eduresurse.gov.md/ru/catalog"` |
| `--resource-types` | Comma-separated resource type filters: video, audio, pdf, doc, archive, image, html, other | string | None | `--resource-types video,pdf,doc` |
| `--education-category-id` | EduResurse education_category_id filter (numeric ID) | string | None | `--education-category-id 1` |
| `--degree-id` | EduResurse degree_id filter (numeric ID) | string | None | `--degree-id 2` |
| `--discipline-id` | EduResurse discipline_id filter (numeric ID) | string | None | `--discipline-id 37` |
| `--catalog-type` | EduResurse catalog type query (e.g., pdf_textbook, video, doc) | string | None | `--catalog-type pdf_textbook` |

**Default EduResurse URL**: `https://eduresurse.gov.md/ru/catalog`

**Resource Types**: video, audio, pdf, doc, archive, image, html, other, download

---

## Subject Aliases

The tool supports comprehensive subject name aliases for all three sources. Aliases are case-insensitive and accept Romanian, English, and Russian names.

### CTICE Subjects (and Default Aliases)

| Canonical Name | Aliases |
|---|---|
| `matematica` | matematica, math, mat, математика, mate |
| `fizica` | fizica, physics, физика |
| `chimie` | chimie, chemistry, химия |
| `biologie` | biologie, biology |
| `geografie` | geografie, geography |
| `istorie` | istorie, history, история |
| `informatica` | informatica, computer science, it |
| `limba engleza` | engleza, english, limba engleza, en |
| `limba franceza` | franceza, french, limba franceza, fr |
| `limba romana` | limba romana, romana, romanian, ro |
| `limba rusa` | limba rusa, rusa, russian, ru |
| `limba bulgara` | limba bulgara, bulgara, bulgarian, bg |
| `limba gagauza` | limba gagauza, gagauza, gagauz, gag |
| `limba ucraineana` | limba ucraineana, ucraineana, ukrainian, ukr, ucr |
| `literatura` | literatura, literature |

### ANCE Subjects (and Default Aliases)

| Canonical Name | Aliases |
|---|---|
| `matematica` | mat, math, matematica, математика |
| `fizica` | fiz, fizica, physics |
| `chimie` | chi, chim, chimie, chemistry |
| `biologie` | bio, biologie, biology |
| `geografie` | geo, geografie, geography |
| `istorie` | ist, istorie, history, история |
| `informatica` | inf, informatica, computer science |
| `limba engleza` | len, en, english, engleza, limba engleza |
| `limba franceza` | lfr, limba franceza, franceza, french, fr |
| `limba romana` | llro, llroal, limba romana, romana, romanian, ro |
| `limba rusa` | llru, limba rusa, rusa, russian, ru |
| `limba bulgara` | llbg, limba bulgara, bulgara, bulgarian, bg |
| `limba gagauza` | llgag, limba gagauza, gagauza, gagauz |
| `limba ucraineana` | llucr, limba ucraineana, ucraineana, ukrainian, ukr, ucr |
| `literatura` | litt, lit, literatura, literature |
| `cultura` | cult, cultura |
| `pregatire sportiva` | prsp, pregatire sportiva, sport |
| `istoria artei plastice` | istartpl, istoria artei plastice, arta plastica |
| `istoria artei teatrale` | istartteatr, istoria artei teatrale, arta teatrala |
| `istoria dansului bulgar` | istdansbulg, istoria dansului bulgar, dansul bulgar |

---

## Output Templates

### JSON Format

All output is in JSON format with an array of resource objects.

#### CTICE Record Template

```json
{
  "class_name": "Clasa a IX-a",
  "class_number": 9,
  "title": "Matematica - Manual",
  "language": "romanian",
  "subject": "matematica",
  "url": "https://ctice.gov.md/files/...",
  "filename": "Matematica_Manual.pdf"
}
```

#### ANCE Record Template

```json
{
  "class_number": 9,
  "title": "ANCE 2024 - Matematica Test",
  "language": "romanian",
  "subject": "matematica",
  "year": 2024,
  "session": "sb",
  "kind": "test",
  "kind_variant": "Sesiunea de bază",
  "url": "https://ance.gov.md/...",
  "filename": "ANCE_2024_matematica_test.pdf"
}
```

#### EduResurse Record Template

```json
{
  "title": "Video: Ecuații de Gradul 2",
  "language": "romanian",
  "subject": "matematica",
  "resource_type": "video",
  "url": "https://eduresurse.gov.md/resource/123",
  "filename": "Video_Ecuatii_Gradul_2.mp4",
  "education_category_id": 1,
  "degree_id": 2,
  "discipline_id": 37
}
```

### Complete JSON Output Example

```json
[
  {
    "class_name": "Clasa a IX-a",
    "class_number": 9,
    "title": "Matematica. Algebra. Manual pentru clasa a IX-a",
    "language": "romanian",
    "subject": "matematica",
    "url": "https://ctice.gov.md/files/Clasa%20a%20IX-a/Matematica/Manual.pdf",
    "filename": "Matematica_Algebra_Manual.pdf"
  },
  {
    "class_number": 9,
    "title": "ANCE 2024 Sesiunea de Bază - Matematica (Test)",
    "language": "romanian",
    "subject": "matematica",
    "year": 2024,
    "session": "sb",
    "kind": "test",
    "kind_variant": "Sesiunea de bază",
    "url": "https://ance.gov.md/files/2024/test.pdf",
    "filename": "ANCE_2024_matematica_test.pdf"
  }
]
```

---

## Examples

### CTICE Examples

#### 1. Get all math manuals for grade 9

```bash
edu-md --ctice --classes 9 --search matematica --info
```

**Output**: JSON file with all grade 9 mathematics manuals (info only, no download)

#### 2. Download English language textbooks for classes 5-8

```bash
edu-md --ctice --classes 5:8 --languages en --output ctice_english_textbooks.json
```

**Output**: Downloads English textbooks to `./downloads/`, results in `ctice_english_textbooks.json`

#### 3. Get all CTICE content for a specific custom URL

```bash
edu-md --ctice-url "https://custom.url/page" --output ./results/books.json
```

---

### ANCE Examples

#### 1. Download all 2024 basic session math tests for grade 9

```bash
edu-md --ance --classes 9 --years 2024 --session sb --kind test --search matematica
```

#### 2. Get all ANCE content (all classes, all years, all sessions)

```bash
edu-md --ance --all --output ance_all.json --info
```

#### 3. Fetch practice tests for grades 4 and 12, multiple years

```bash
edu-md --ance --classes 4,12 --years 2022-2024 --session exer --download-workers 3
```

#### 4. Get answer keys (barem) for supplementary session 2023

```bash
edu-md --ance --years 2023 --session ss --kind barem --info --output ance_answer_keys.json
```

---

### EduResurse Examples

#### 1. Search for video resources on mathematics

```bash
edu-md --eduresurse --search matematica --resource-types video --info
```

#### 2. Filter by discipline and education category

```bash
edu-md --eduresurse --discipline-id 37 --education-category-id 1 --output eduresurse_results.json
```

#### 3. Get PDF textbooks with specific degree filter

```bash
edu-md --eduresurse --resource-types pdf --degree-id 2 --info --output eduresurse_pdfs.json
```

#### 4. Custom EduResurse URL with parameters

```bash
edu-md --eduresurse-url "https://eduresurse.gov.md/ru/catalog?type=video" --search fizica --languages ru
```

---

### Combined & All-Source Examples

#### 1. Download all mathematics materials from all sources

```bash
edu-md --all --classes 9 --search matematica --download-delay 2.0
```

**Output**: Three separate JSON files:
- `downloads/edu_md_results_ctice.json`
- `downloads/edu_md_results_ance.json`
- `downloads/edu_md_results_eduresurse.json`

#### 2. Fetch Romanian language materials from CTICE and ANCE only

```bash
edu-md --ctice --ance --classes 5,6,7,8,9 --languages ro --info --output language_materials.json
```

#### 3. Interactive mode (no command-line arguments)

```bash
edu-md --interactive
```

**Output**: Step-by-step menu for choosing sources, filters, and output options

---

### Parallel Download Examples

#### 1. Fast download with 5 workers, minimal delay

```bash
edu-md --ctice --classes 9 --download-workers 5 --download-delay 1.0
```

#### 2. Conservative download (1 worker, long delay) for rate-limiting

```bash
edu-md --ance --years 2024 --download-workers 1 --download-delay 5.0
```

---

### Advanced Examples

#### 1. Get all Romanian math/physics content and save metadata to a custom path

```bash
edu-md --ctice --ance --classes 9 --search "matematica,fizica" --languages ro \
  --output ./results/combined_results.json
```

#### 2. Download EduResurse resources with SSL fallback (for problematic servers)

```bash
edu-md --eduresurse --search matematica --insecure-ssl --download-workers 2
```

#### 3. Fetch all content and save to different output files per source

```bash
edu-md --all --classes 9 --output ./results/ --info
```

**Output**: Creates separate files automatically:
- `./results/edu_md_results_ctice.json`
- `./results/edu_md_results_ance.json`
- `./results/edu_md_results_eduresurse.json`

#### 4. Class range with multiple filters

```bash
edu-md --ctice --classes 5-9 --search "matematica,fizica,chimie" --languages "ro,en" \
  --download-workers 4 --output textbooks.json
```

---

## How to Work

### Installation & Setup

```bash
git clone https://github.com/Dan-Kert/edu-md.git
cd edu-md

python -m venv .venv
source .venv/bin/activate

pip install -e .
```

### Basic Workflow

**Step 1**: Identify your source(s)
- CTICE for curriculum manuals
- ANCE for examination tests
- EduResurse for general educational resources

**Step 2**: Define filters
- `--classes`: Specific grades (CTICE: any; ANCE: 4, 9, 12 only)
- `--search`: Subject name or keyword
- `--languages`: Language preference
- `--years`: For ANCE only

**Step 3**: Choose between info or download mode
- By default: files are automatically downloaded
- Use `--info` flag to fetch only metadata (skip downloading)

**Step 4**: Adjust download performance (if needed)
- `--download-workers`: Increase for parallel downloads (default: 1)
- `--download-delay`: Pause between downloads for rate-limiting (default: 3.0 seconds)

**Step 5**: Get output
- Results in JSON format at `--output` path

### Output Files

- **Metadata file**: Contains resource information (always generated)
- **Downloaded files**: Saved to `./downloads/` relative to the current working directory. The CLI has no directory flag; choose a different working directory when needed.
  - Filenames are sanitized (special characters replaced with underscores)
  - Maximum filename length: 180 characters
  - Organized by source when using `--all`

### Filtering Strategy

**Most Specific to Least Specific**:

1. Subject (fastest): `--search matematica`
2. Language + Class: `--languages ro --classes 9`
3. Class only: `--classes 9` (may return many results)
4. All content: Use `--all` with caution (can be large)

---

## Error Handling & Troubleshooting

### Common Issues

#### SSL Certificate Errors

```
requests.exceptions.SSLError: ...
```

**Solution**: Use `--insecure-ssl` flag (with caution)

```bash
edu-md --ctice --search matematica --insecure-ssl
```

#### Download Rate Limiting / 429 Errors

**Solution**: Increase delay between downloads

```bash
edu-md --ance --years 2024 --download-delay 5.0 --download-workers 1
```

#### No Results Found

**Solution**: Verify subject alias or try broader search

```bash
# Try exact subject name
edu-md --ctice --search "limba engleza" --info

# Or use alias
edu-md --ctice --search engleza --info
```

#### ANCE Returns No Results

**Reasons**:
- Requested year not available for selected class
- Class not in {4, 9, 12}
- Session not available for selected year

**Solution**: Use `--info` first to preview available content

---

## Output Field Reference

### Common Fields (All Sources)

- `title` (string): Resource name/title
- `language` (string): Detected language (romanian, russian, english, french, gagauz, bulgarian, ukrainian)
- `subject` (string): Detected or categorized subject
- `url` (string): Direct download link
- `filename` (string): Suggested filename for download

### CTICE-Specific Fields

- `class_name` (string): Romanian class name (e.g., "Clasa a IX-a")
- `class_number` (integer): Grade level (1-12)

### ANCE-Specific Fields

- `class_number` (integer): Grade level (4, 9, 12)
- `year` (integer): Exam year
- `session` (string): Session type (sb, ss, pret, exer)
- `kind` (string): Document type (test or barem)
- `kind_variant` (string): Human-readable session name

### EduResurse-Specific Fields

- `resource_type` (string): Type of resource (video, audio, pdf, doc, etc.)
- `education_category_id` (string): Category identifier
- `degree_id` (string): Degree level identifier
- `discipline_id` (string): Discipline identifier

---

## Requirements

- Python 3.9+
- Dependencies:
  - `requests` (>=2.32.0) - HTTP requests
  - `beautifulsoup4` (>=4.13.0) - HTML parsing
  - `urllib3` - URL utilities

Install all dependencies:

```bash
pip install -r requirements.txt
```
---