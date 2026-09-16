"""
File Management Subsystem
Granular file capabilities for TXT, PDF, DOCX, XLSX, CSV, JSON, PPTX, ZIP and
images, plus folders, search and in-file content search.

Convention:
- Destructive operations (delete, overwrite, move-over) require `confirm=True`.
- Paths may be absolute or relative; relative paths resolve against the agent
  workspace root. User-home paths use "~/..." syntax (e.g. "~/Documents/resume.pdf").
"""

import os
import csv
import io
import json
import shutil
import zipfile
from pathlib import Path
from typing import Dict, Any, List, Optional

WORKSPACE_DIR = Path(__file__).resolve().parent.parent.parent


def _resolve(path: str) -> Path:
    """Expands ~ and resolves relative paths against the agent workspace."""
    p = str(path).strip().strip('"').strip("'")
    if p.startswith("~"):
        return Path(p).expanduser()
    p = Path(p)
    if p.is_absolute():
        return p
    return WORKSPACE_DIR / p


def _ok(path: Path) -> bool:
    return path.exists()


def _result(success: bool, output: str = "", **extra) -> Dict[str, Any]:
    return {"success": success, "output": output, **extra}


# ==========================================================
# SEARCH / DISCOVERY
# ==========================================================
def search_files(pattern: str, directory: str = None, recursive: bool = True, case_sensitive: bool = False) -> Dict[str, Any]:
    """
    Finds files matching a glob pattern (e.g. "*.pdf", "**/project/**/*.py").
    """
    base = _resolve(directory) if directory else WORKSPACE_DIR
    if not base.exists():
        return _result(False, f"Directory not found: {base}", directory=str(base))
    glob_fn = base.rglob if recursive else base.glob
    matches = []
    try:
        for item in glob_fn(str(pattern)):
            if item.is_file():
                matches.append({
                    "path": str(item),
                    "name": item.name,
                    "size_kb": round(item.stat().st_size / 1024, 1),
                })
    except Exception as e:
        return _result(False, f"Search failed: {e}")
    return _result(True, f"Found {len(matches)} file(s) matching '{pattern}'.", files=matches, count=len(matches))


def list_directory(directory: str = ".", show_hidden: bool = False) -> Dict[str, Any]:
    """Lists entries in a directory."""
    base = _resolve(directory)
    if not base.exists() or not base.is_dir():
        return _result(False, f"Directory not found: {base}", directory=str(base))
    items = []
    try:
        for item in base.iterdir():
            if item.name.startswith(".") and not show_hidden:
                continue
            try:
                size = round(item.stat().st_size / 1024, 1) if item.is_file() else 0
            except OSError:
                size = 0
            items.append({"name": item.name, "is_dir": item.is_dir(), "size_kb": size})
    except Exception as e:
        return _result(False, f"Failed to list directory: {e}")
    return _result(True, f"Found {len(items)} item(s).", directory=str(base), items=items, count=len(items))


def search_inside_files(term: str, directory: str = None, extensions: List[str] = None, max_results: int = 30) -> Dict[str, Any]:
    """Content search: scans text-like files for a keyword/phrase."""
    if not term:
        return _result(False, "No search term provided.")
    base = _resolve(directory) if directory else WORKSPACE_DIR
    exts = extensions or [".txt", ".md", ".json", ".py", ".js", ".ts", ".html", ".css", ".csv", ".log", ".xml", ".yaml", ".yml", ".ini", ".cfg"]
    results = []
    for item in base.rglob("*"):
        if not item.is_file() or item.suffix.lower() not in exts:
            continue
        try:
            with open(item, "r", encoding="utf-8", errors="ignore") as f:
                for lineno, line in enumerate(f, 1):
                    if term.lower() in line.lower():
                        results.append({"file": str(item), "line": lineno, "snippet": line.strip()[:200]})
                        if len(results) >= max_results:
                            break
        except Exception:
            continue
        if len(results) >= max_results:
            break
    return _result(True, f"Found {len(results)} match(es) for '{term}'.", term=term, matches=results, count=len(results))


def get_file_info(path: str) -> Dict[str, Any]:
    """Returns metadata for a file or folder."""
    p = _resolve(path)
    if not _ok(p):
        return _result(False, f"Not found: {p}", path=str(p))
    stat = p.stat()
    return _result(True, f"Info for {p.name}.", path=str(p), info={
        "name": p.name,
        "is_dir": p.is_dir(),
        "size_bytes": stat.st_size,
        "size_kb": round(stat.st_size / 1024, 1),
        "modified": stat.st_mtime,
        "created": stat.st_ctime,
        "parent": str(p.parent),
    })


# ==========================================================
# READERS (format-aware)
# ==========================================================
def read_file(path: str, max_chars: int = 6000) -> Dict[str, Any]:
    """Reads plain text / markdown / code files."""
    p = _resolve(path)
    if not _ok(p):
        return _result(False, f"File not found: {p}")
    try:
        content = p.read_text(encoding="utf-8", errors="ignore")[:max_chars]
        return _result(True, f"Read {p.name} ({len(content.splitlines())} lines).", content=content, path=str(p))
    except Exception as e:
        return _result(False, f"Failed to read: {e}")


def read_pdf(path: str, max_pages: int = 20) -> Dict[str, Any]:
    """Extracts text from a PDF file (pypdf)."""
    p = _resolve(path)
    if not _ok(p):
        return _result(False, f"File not found: {p}")
    try:
        from pypdf import PdfReader
    except ImportError:
        return _result(False, "pypdf is not installed. Run: pip install pypdf")
    try:
        reader = PdfReader(str(p))
        pages = []
        for i, page in enumerate(reader.pages):
            if i >= max_pages:
                break
            pages.append({"page": i + 1, "text": (page.extract_text() or "").strip()})
        return _result(True, f"Extracted {len(pages)} page(s) from {p.name}.", pages=pages, page_count=len(pages))
    except Exception as e:
        return _result(False, f"Failed to read PDF: {e}")


def read_docx(path: str) -> Dict[str, Any]:
    """Extracts paragraphs from a DOCX file (python-docx)."""
    p = _resolve(path)
    if not _ok(p):
        return _result(False, f"File not found: {p}")
    try:
        from docx import Document
    except ImportError:
        return _result(False, "python-docx is not installed. Run: pip install python-docx")
    try:
        doc = Document(str(p))
        paragraphs = [para.text for para in doc.paragraphs if para.text.strip()]
        tables = [[[cell.text for cell in row.cells] for row in table.rows] for table in doc.tables]
        return _result(True, f"Read {p.name} ({len(paragraphs)} paragraphs).", paragraphs=paragraphs, tables=tables)
    except Exception as e:
        return _result(False, f"Failed to read DOCX: {e}")


def read_xlsx(path: str, sheet: str = None) -> Dict[str, Any]:
    """Reads an XLSX workbook into rows of values (openpyxl)."""
    p = _resolve(path)
    if not _ok(p):
        return _result(False, f"File not found: {p}")
    try:
        from openpyxl import load_workbook
    except ImportError:
        return _result(False, "openpyxl is not installed. Run: pip install openpyxl")
    try:
        wb = load_workbook(str(p), data_only=True, read_only=True)
        sheet_name = sheet or wb.sheetnames[0]
        ws = wb[sheet_name]
        rows = [list(row) for row in ws.iter_rows(values_only=True)]
        return _result(True, f"Read sheet '{sheet_name}' ({len(rows)} rows).", sheet=sheet_name, sheets=wb.sheetnames, rows=rows)
    except Exception as e:
        return _result(False, f"Failed to read XLSX: {e}")


def read_csv(path: str, delimiter: str = ",") -> Dict[str, Any]:
    """Reads a CSV/TSV file."""
    p = _resolve(path)
    if not _ok(p):
        return _result(False, f"File not found: {p}")
    try:
        with open(p, "r", encoding="utf-8", errors="ignore", newline="") as f:
            reader = csv.reader(f, delimiter=delimiter)
            rows = [row for row in reader]
        return _result(True, f"Read {len(rows)} row(s) from {p.name}.", rows=rows, row_count=len(rows))
    except Exception as e:
        return _result(False, f"Failed to read CSV: {e}")


def read_json(path: str) -> Dict[str, Any]:
    """Reads and parses a JSON file."""
    p = _resolve(path)
    if not _ok(p):
        return _result(False, f"File not found: {p}")
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return _result(True, f"Parsed {p.name}.", data=data)
    except Exception as e:
        return _result(False, f"Failed to parse JSON: {e}")


def read_pptx(path: str) -> Dict[str, Any]:
    """Extracts text from a PPTX presentation (python-pptx)."""
    p = _resolve(path)
    if not _ok(p):
        return _result(False, f"File not found: {p}")
    try:
        from pptx import Presentation
    except ImportError:
        return _result(False, "python-pptx is not installed. Run: pip install python-pptx")
    try:
        prs = Presentation(str(p))
        slides = []
        for i, slide in enumerate(prs.slides, 1):
            text = "\n".join(shape.text for shape in slide.shapes if hasattr(shape, "text") and shape.text.strip())
            slides.append({"slide": i, "text": text})
        return _result(True, f"Read {len(slides)} slide(s).", slides=slides)
    except Exception as e:
        return _result(False, f"Failed to read PPTX: {e}")


def read_zip(path: str, max_entries: int = 100) -> Dict[str, Any]:
    """Lists the contents of a ZIP archive."""
    p = _resolve(path)
    if not _ok(p):
        return _result(False, f"File not found: {p}")
    try:
        with zipfile.ZipFile(str(p)) as zf:
            names = zf.namelist()[:max_entries]
            return _result(True, f"'{p.name}' contains {len(names)}+ entries.", entries=names, entry_count=len(names))
    except Exception as e:
        return _result(False, f"Failed to read ZIP: {e}")


# ==========================================================
# WRITERS / EDITORS
# ==========================================================
def create_file(path: str, content: str, overwrite: bool = False, confirm: bool = False) -> Dict[str, Any]:
    """Creates a new text/code file. Overwrites only with confirm=True."""
    p = _resolve(path)
    if _ok(p) and not (overwrite and confirm):
        return _result(False, f"File already exists: {p}. Pass overwrite=True and confirm=True to replace it.")
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return _result(True, f"Created '{p.name}' ({p.stat().st_size} bytes).", path=str(p))
    except Exception as e:
        return _result(False, f"Failed to create file: {e}")


def create_csv(path: str, rows: List[List[Any]], headers: List[str] = None, delimiter: str = ",") -> Dict[str, Any]:
    """Creates a CSV file from a list of rows (and optional header row)."""
    p = _resolve(path)
    if not rows and not headers:
        return _result(False, "Provide headers or rows to write.")
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f, delimiter=delimiter)
            if headers:
                writer.writerow(headers)
            writer.writerows(rows)
        return _result(True, f"Created CSV '{p.name}' with {len(rows)} data row(s).", path=str(p))
    except Exception as e:
        return _result(False, f"Failed to create CSV: {e}")


def create_folder(path: str) -> Dict[str, Any]:
    """Creates a folder (and parents) if it does not exist."""
    p = _resolve(path)
    if p.exists() and p.is_dir():
        return _result(True, f"Folder already exists: {p}", path=str(p), created=False)
    try:
        p.mkdir(parents=True, exist_ok=True)
        return _result(True, f"Created folder '{p}'.", path=str(p), created=True)
    except Exception as e:
        return _result(False, f"Failed to create folder: {e}")


def edit_file(path: str, new_content: str = None, replace: str = None, replacement: str = "", append: str = None, confirm: bool = False) -> Dict[str, Any]:
    """Edits a text file: replace substring, append text, or rewrite entirely."""
    p = _resolve(path)
    if not _ok(p):
        return _result(False, f"File not found: {p}")
    try:
        original = p.read_text(encoding="utf-8", errors="ignore")
        if new_content is not None:
            updated = new_content
            mode = "rewrote"
        elif replace is not None:
            if replace not in original:
                return _result(False, f"Text to replace was not found in {p.name}.")
            updated = original.replace(replace, replacement)
            mode = "replaced text"
        elif append is not None:
            updated = original + append
            mode = "appended text"
        else:
            return _result(False, "Nothing to edit. Provide new_content, replace+replacement, or append.")
        p.write_text(updated, encoding="utf-8")
        return _result(True, f"Edited {p.name} ({mode}).", path=str(p), mode=mode)
    except Exception as e:
        return _result(False, f"Failed to edit file: {e}")


# ==========================================================
# DESTRUCTIVE / ORGANIZATIONAL (require confirmation)
# ==========================================================
def delete_file(path: str, confirm: bool = False) -> Dict[str, Any]:
    """Deletes a file. Requires confirm=True (destructive)."""
    p = _resolve(path)
    if not _ok(p):
        return _result(False, f"File not found: {p}")
    if not confirm:
        return _result(False, f"Refusing to delete '{p}' without confirmation. Retry with confirm=True.")
    try:
        p.unlink()
        return _result(True, f"Deleted '{p.name}'.")
    except Exception as e:
        return _result(False, f"Failed to delete: {e}")


def move_file(source: str, destination: str, confirm: bool = False) -> Dict[str, Any]:
    """Moves/renames a file into a new location."""
    src = _resolve(source)
    if not _ok(src):
        return _result(False, f"Source not found: {src}")
    dst = _resolve(destination)
    if dst.exists() and dst.is_dir():
        dst = dst / src.name
    if dst.exists() and not confirm:
        return _result(False, f"Destination already exists: {dst}. Pass confirm=True to overwrite.")
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        return _result(True, f"Moved '{src.name}' to '{dst}'.", from_path=str(src), to_path=str(dst))
    except Exception as e:
        return _result(False, f"Failed to move: {e}")


def rename_file(path: str, new_name: str, confirm: bool = False) -> Dict[str, Any]:
    """Renames a file in place."""
    p = _resolve(path)
    if not _ok(p):
        return _result(False, f"File not found: {p}")
    parent = p.parent
    new_path = parent / new_name
    if _ok(new_path) and not confirm:
        return _result(False, f"A file named '{new_name}' already exists here. Pass confirm=True to overwrite.")
    try:
        p.rename(new_path)
        return _result(True, f"Renamed '{p.name}' to '{new_name}'.", from_path=str(p), to_path=str(new_path))
    except Exception as e:
        return _result(False, f"Failed to rename: {e}")


def open_file(path: str) -> Dict[str, Any]:
    """Opens a file with the default Windows application."""
    from app.integrations.app_launcher import open_file_with_default_app
    return open_file_with_default_app(path)


# ==========================================================
# CONVERSIONS
# ==========================================================
def convert_file(source: str, target_format: str, destination: str = None) -> Dict[str, Any]:
    """
    Converts between supported families:
      csv -> json | xlsx
      json -> csv
      txt | md -> html
    """
    src = _resolve(source)
    if not _ok(src):
        return _result(False, f"Source not found: {src}")
    fmt = target_format.lower().lstrip(".")
    ext = src.suffix.lower()

    def _write(dst: Path, text: str) -> None:
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(text, encoding="utf-8")

    try:
        if ext == ".csv" and fmt == "json":
            with open(src, "r", encoding="utf-8", errors="ignore", newline="") as f:
                rows = list(csv.reader(f))
            headers = rows[0] if rows else []
            data = [dict(zip(headers, row)) for row in rows[1:]] if headers else rows
            dst = _resolve(destination or src.with_suffix(".json"))
            dst.write_text(json.dumps(data, indent=2), encoding="utf-8")
            return _result(True, f"Converted {src.name} to JSON.", to_path=str(dst))

        if ext == ".csv" and fmt == "xlsx":
            try:
                from openpyxl import Workbook
            except ImportError:
                return _result(False, "openpyxl is not installed. Run: pip install openpyxl")
            with open(src, "r", encoding="utf-8", errors="ignore", newline="") as f:
                rows = list(csv.reader(f))
            wb = Workbook()
            ws = wb.active
            for row in rows:
                ws.append(row)
            dst = _resolve(destination or src.with_suffix(".xlsx"))
            wb.save(str(dst))
            return _result(True, f"Converted {src.name} to XLSX.", to_path=str(dst))

        if ext == ".json" and fmt == "csv":
            data = json.loads(src.read_text(encoding="utf-8"))
            items = data if isinstance(data, list) else [data]
            rows = []
            for item in items:
                if isinstance(item, dict):
                    rows.append([str(v) for v in item.values()])
            headers = list(items[0].keys()) if items and isinstance(items[0], dict) else ["value" for _ in items]
            dst = _resolve(destination or src.with_suffix(".csv"))
            out = create_csv(dst, rows, headers=headers)
            return {**out, "to_path": str(dst)} if out.get("success") else out

        if ext in (".txt", ".md") and fmt in ("html", "htm"):
            body = src.read_text(encoding="utf-8", errors="ignore")
            html = f"<!DOCTYPE html><html><head><meta charset='utf-8'><title>{src.stem}</title></head><body><pre>{_html_escape(body)}</pre></body></html>"
            dst = _resolve(destination or src.with_suffix(".html"))
            _write(dst, html)
            return _result(True, f"Converted {src.name} to HTML.", to_path=str(dst))

        return _result(False, f"Unsupported conversion: {ext} -> .{fmt}. Supported: csv->json, csv->xlsx, json->csv, txt/md->html.")
    except Exception as e:
        return _result(False, f"Conversion failed: {e}")


def _html_escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")