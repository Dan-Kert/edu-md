# CTICE Parser & Downloader 📚

A Python-based command-line utility for automated metadata parsing, filtering, and bulk downloading of digital school textbooks from the official **CTICE (Centrul Tehnologiilor Informaționale și Comunicaționale în Educație)** portal of the Ministry of Education of the Republic of Moldova.

The script scrapes the website pages, structures chaotic HTML lists into clean JSON/CSV formats, automatically detects the language and school subject of each book, and securely downloads files by bypassing broken SSL certificate chains on the government distribution server.

---

## ✨ Key Features

* 🔄 **On-the-Fly Parsing:** Extracts direct links to PDF files natively from CTICE repository pages.
* 🤖 **Smart Tagging:** Converts Roman numeral grades to Arabic integers (`XI` ➡️ `11`), and detects languages and subjects using advanced text pattern matching.
* 🛠️ **Advanced CLI:** Manage filters, grade ranges, output formats, and target storage directories directly from your terminal.
* ⚡ **SSL Error Bypass:** Automatically suppresses `InsecureRequestWarning` logs for uninterrupted operation across Linux and Windows environments.
* 🧼 **Filename Sanitization:** Automatically renames downloaded files, stripping away characters prohibited by operating systems.

---

## ⚙️ CLI Options & Core Logic

The script is entirely managed via command-line interface (CLI) arguments. This enables full pipeline automation and granular filtering without modifying the source code.

### 1. Complete List of Available Flags

| Flag | Data Type | Default Value | Description & Operational Logic |
| :--- | :--- | :--- | :--- |
| `--url` | `str` | `https://ctice.gov.md/?page_id=447` | The target root URL containing the lists of textbooks. |
| `--classes` | `str` | `None` | Comma-separated list of grades (e.g., `8,9,11`). Also supports range syntax via colons (`5:8`), which automatically expands to `5,6,7,8`. |
| `--grade-range` | `str` | `None` | An alternative way to define an inclusive grade range (e.g., `10:12`). Results merge with the `--classes` flag. |
| `--keywords` | `str` | `None` | Comma-separated keywords to search across titles, subjects, or categories (e.g., `fizica,chimie`). |
| `--languages` | `str` | `None` | Strict comma-separated filter for textbook languages (`russian,romanian`). |
| `--format` | `choice` | `json` | Chooses the structured data output format: `json` or `csv`. |
| `--output` | `str` | `None` | The output file path to save results. If omitted, structured text prints directly to `stdout`. |
| `--download` | `flag` | Disabled | A boolean trigger. When passed, activates the physical downloading of PDF files to local storage. |
| `--download-dir`| `str` | `./downloads` | The destination directory where downloaded PDFs will be stored. |

---

### 2. Filter Operations (Combining Flags)

To write efficient textbook queries, it is essential to understand the internal evaluation logic of the filters:

* **Logical AND between different flags:** 
  If you specify `--classes 9 --languages russian --keywords "matematica"`, the script will isolate only the books matching **all three conditions simultaneously** (Grade 9 **AND** Russian language **AND** Mathematics).
* **Logical OR within a single flag:** 
  When listing comma-separated values inside a single parameter, the script triggers a match if **at least one** value matches.
  * `--languages russian,romanian` ➡️ extracts both Russian and Romanian textbooks.
  * `--keywords "fizica,chimie"` ➡️ extracts books matching either physics **OR** chemistry.

---

### 3. Execution Modes

Depending on your pipeline goals, the script operates in two distinct execution modes:

#### Mode A: Metadata Analysis & Extraction (No-Download)
Used to generate textbook indices, verify remote layout changes, or build a local database. The `--download` flag is **omitted**.
* **Console Output (Default):** Ideal for rapid evaluations. Structured data prints directly to `stdout`.
* **File Export:** If `--output ./data/report.json` is passed, the script handles directory allocation and writes a formatted file.

#### Mode B: Bulk Downloader (Physical Storage Fetch)
Used to mirror files locally to your machine. The `--download` flag **must be supplied**.
* The engine resolves your filters, computes the target download manifest, and sends consecutive `GET` streams.
* Prior to writing data to your disk, each target file path is sanitized via a regex layer that replaces unsafe characters with underscores `_`, mitigating filename runtime exceptions across Linux and Windows.

---

## 🗂️ Supported Classifiers: Subjects & Languages

The parsing engine uses deterministic token analytics to categorize books. Use these precise values (comma-separated, without trailing spaces) when querying with `--keywords` or `--languages`.

### 1. Recognized Subjects (`--keywords`)
Matches run against the raw title, scraped category metadata, and calculated subject keys. You can target these indices:

* **STEM / Hard Sciences:**
  * `matematica` — Mathematics
  * `informatica` — Computer Science / Informatics
  * `fizica` — Physics
  * `chimie` — Chemistry
  * `biologie` — Biology
  * `geografie` — Geography
* **Humanities & Language Arts:**
  * `istorie` — History
  * `abecedar` — Primer / Alphabet Book / Abecedar
  * `literatura universala` — World Literature
  * `limba romana` / `limba si literatura romana` — Romanian Language & Literature
  * `limba rusa` / `limba si literatura rusa` — Russian Language & Literature
  * `limba engleza` / `english` — English Language
  * `limba franceza` / `français` — French Language
  * `limba gagauza` / `gagauz` — Gagauz Language
  * `limba bulgara` / `bulgar` — Bulgarian Language
  * `limba ucraineana` / `ucrain` — Ukrainian Language
* **Arts & Applied Technologies:**
  * `educatie muzicala` — Music Education
  * `educatie plastica` — Fine Arts / Plastic Education
  * `educatie tehnologica` — Technological / Manual Arts Education
* **Miscellaneous:**
  * `other` — Any secondary course that falls outside the native lexer templates above.

### 2. Supported Languages (`--languages`)
Strict boundaries for separating regional educational tracks:

* `romanian` — Textbooks published in Romanian
* `russian` — Textbooks published in Russian
* `english` — Textbooks published in English
* `french` — Textbooks published in French
* `gagauz` — Textbooks published in Gagauz
* `bulgarian` — Textbooks published in Bulgarian
* `ukrainian` — Textbooks published in Ukrainian
* `unknown` — Triggered when the script cannot safely isolate language patterns from the title asset

---

## 🚀 Requirements & Installation

The code runs on standard Python 3.8+ environments and relies on minimal external packaging layers.

```bash
git clone https://github.com/Dan-Kert/mdbooks
```

```bash
pip install -r requirements.txt
```