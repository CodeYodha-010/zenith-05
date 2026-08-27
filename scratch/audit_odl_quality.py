"""
OpenDataLoader vs PyMuPDF — PDF Parsing Quality Audit
"""
import opendataloader_pdf
import fitz
import tempfile
import os
import re
import time
from pathlib import Path
from collections import Counter

PDF_DIR = r"C:\Zenith1\rag_project\Knowlegebase\rag_documents\rag_documents"

PDFS = [
    "Appendix_4R_RoDTEP_Schedule.pdf",
    "DGFT_Notification_62_Wheat_Quota.pdf",
    "CBIC_Customs_Manual_2023.pdf",
    "FTP2023_Chapter11_Definitions.pdf",
]


def odl_parse(pdf_path):
    with tempfile.TemporaryDirectory(prefix="odl_audit_") as tmp:
        t0 = time.time()
        opendataloader_pdf.convert(
            input_path=[pdf_path],
            output_dir=tmp,
            format="markdown",
            quiet=True,
        )
        elapsed = time.time() - t0
        md_files = list(Path(tmp).glob("*.md"))
        if not md_files:
            return "", elapsed
        with open(md_files[0], 'r', encoding='utf-8') as f:
            return f.read(), elapsed


def pymupdf_parse(pdf_path):
    t0 = time.time()
    doc = fitz.open(pdf_path)
    pages = []
    for page in doc:
        pages.append(page.get_text())
    doc.close()
    elapsed = time.time() - t0
    return '\n'.join(pages), elapsed


def count_tables_md(text):
    table_lines = [l for l in text.split('\n') if '|' in l and re.search(r'\|.*\|', l)]
    separators = [l for l in table_lines if re.match(r'\s*\|[\s\-:|]+\|\s*$', l)]
    return len(separators)


def count_headings(text):
    return len(re.findall(r'^#{1,6}\s+', text, re.MULTILINE))


def count_numbered_lists(text):
    return len(re.findall(r'^\s*\d+[\.\)]\s', text, re.MULTILINE))


def word_coverage(odl_text, pymupdf_text):
    odl_words = set(re.findall(r'\b[a-zA-Z]{4,}\b', odl_text.lower()))
    pymupdf_words = set(re.findall(r'\b[a-zA-Z]{4,}\b', pymupdf_text.lower()))
    if not pymupdf_words:
        return {"coverage": 0, "odl_unique": 0, "pymupdf_unique": 0}
    coverage = len(odl_words & pymupdf_words) / len(pymupdf_words)
    return {
        "coverage": coverage,
        "odl_unique": len(odl_words - pymupdf_words),
        "pymupdf_unique": len(pymupdf_words - odl_words),
    }


def find_sample_tables_odl(text, n=2):
    tables = []
    in_table = False
    current = []
    for line in text.split('\n'):
        if '|' in line and re.search(r'\|.*\|', line):
            in_table = True
            current.append(line)
        else:
            if in_table and current:
                tables.append('\n'.join(current))
                if len(tables) >= n:
                    break
                current = []
            in_table = False
    if current and len(tables) < n:
        tables.append('\n'.join(current))
    return tables


def find_sample_headings_odl(text, n=8):
    headings = re.findall(r'^(#{1,6}\s+.+)$', text, re.MULTILINE)
    return headings[:n]


def check_garbled(text):
    garbled = []
    if '\ufffd' in text:
        garbled.append(f"Unicode replacement char (\\ufffd): {text.count(chr(0xFFFD))} occurrences")
    weird = re.findall(r'[^\x00-\x7F]{10,}', text)
    if weird:
        garbled.append(f"Long non-ASCII sequences: {len(weird)}")
    double_space = len(re.findall(r' {5,}', text))
    if double_space > 10:
        garbled.append(f"Excessive double spacing: {double_space} lines")
    return garbled


# ============================================================
print("=" * 90)
print("  OPENDATALOADER vs PYMUPDF — PDF PARSING QUALITY AUDIT")
print("=" * 90)

results = []

for pdf_name in PDFS:
    pdf_path = os.path.join(PDF_DIR, pdf_name)
    if not os.path.exists(pdf_path):
        print(f"\n[SKIP] {pdf_name} — not found")
        continue

    print(f"\n{'=' * 90}")
    print(f"  FILE: {pdf_name}")
    print(f"{'=' * 90}")

    odl_text, odl_time = odl_parse(pdf_path)
    pymupdf_text, pymupdf_time = pymupdf_parse(pdf_path)

    odl_chars = len(odl_text)
    pymupdf_chars = len(pymupdf_text)

    odl_tables = count_tables_md(odl_text)
    pymupdf_tables = count_tables_md(pymupdf_text)

    odl_headings = count_headings(odl_text)
    pymupdf_headings = count_headings(pymupdf_text)

    odl_lists = count_numbered_lists(odl_text)
    pymupdf_lists = count_numbered_lists(pymupdf_text)

    cov = word_coverage(odl_text, pymupdf_text)

    odl_garbled = check_garbled(odl_text)
    pymupdf_garbled = check_garbled(pymupdf_text)

    # --- Metrics table ---
    print(f"\n  {'METRIC':<40} {'OpenDataLoader':>18} {'PyMuPDF':>18} {'Delta':>12}")
    print("  " + "-" * 88)

    delta_pct = ((odl_chars - pymupdf_chars) / max(pymupdf_chars, 1)) * 100
    print(f"  {'Total characters':<40} {odl_chars:>18,} {pymupdf_chars:>18,} {delta_pct:>+11.1f}%")
    print(f"  {'Parse time (sec)':<40} {odl_time:>18.2f} {pymupdf_time:>18.2f}")
    print(f"  {'Markdown tables detected':<40} {odl_tables:>18} {pymupdf_tables:>18}")
    print(f"  {'Headings (# format)':<40} {odl_headings:>18} {pymupdf_headings:>18}")
    print(f"  {'Numbered list items':<40} {odl_lists:>18} {pymupdf_lists:>18}")
    print(f"  {'Word coverage (ODL vs PyMuPDF)':<40} {'—':>18} {cov['coverage']:>17.1%}")
    print(f"  {'Unique words only in ODL':<40} {cov['odl_unique']:>18,}")
    print(f"  {'Unique words only in PyMuPDF':<40} {cov['pymupdf_unique']:>18,}")

    # --- Sample tables ---
    if odl_tables > 0:
        samples = find_sample_tables_odl(odl_text, 2)
        print(f"\n  --- SAMPLE TABLES (OpenDataLoader markdown) ---")
        for i, t in enumerate(samples, 1):
            lines = t.split('\n')
            print(f"\n    Table {i} ({len(lines)} rows):")
            for line in lines[:8]:
                print(f"      {line}")
            if len(lines) > 8:
                print(f"      ... ({len(lines) - 8} more rows)")

    # --- Sample headings ---
    headings = find_sample_headings_odl(odl_text)
    if headings:
        print(f"\n  --- SAMPLE HEADINGS (OpenDataLoader) ---")
        for h in headings:
            print(f"    {h}")

    # --- Garbled ---
    if odl_garbled:
        print(f"\n  --- GARBLED (OpenDataLoader) ---")
        for g in odl_garbled:
            print(f"    ! {g}")
    if pymupdf_garbled:
        print(f"\n  --- GARBLED (PyMuPDF) ---")
        for g in pymupdf_garbled:
            print(f"    ! {g}")

    # --- Content diff ---
    pymupdf_chunks = set(re.findall(r'\b[a-zA-Z]{4,}\b', pymupdf_text.lower()))
    odl_chunks = set(re.findall(r'\b[a-zA-Z]{4,}\b', odl_text.lower()))
    lost = sorted(pymupdf_chunks - odl_chunks)
    gained = sorted(odl_chunks - pymupdf_chunks)

    if lost and len(lost) > 10:
        print(f"\n  --- CONTENT IN PYMUPDF BUT MISSING FROM ODL (top 15) ---")
        for w in lost[:15]:
            print(f"    * {w}")
        if len(lost) > 15:
            print(f"    ... and {len(lost) - 15} more unique words")

    if gained and len(gained) > 10:
        print(f"\n  --- CONTENT IN ODL BUT MISSING FROM PYMUPDF (top 15) ---")
        for w in gained[:15]:
            print(f"    * {w}")
        if len(gained) > 15:
            print(f"    ... and {len(gained) - 15} more unique words")

    # --- First 500 chars of each for direct comparison ---
    print(f"\n  --- FIRST 600 CHARS: OpenDataLoader ---")
    for line in odl_text[:600].split('\n'):
        print(f"    | {line}")
    print(f"\n  --- FIRST 600 CHARS: PyMuPDF ---")
    for line in pymupdf_text[:600].split('\n'):
        print(f"    | {line}")

    results.append({
        "name": pdf_name,
        "odl_chars": odl_chars,
        "pymupdf_chars": pymupdf_chars,
        "odl_tables": odl_tables,
        "pymupdf_tables": pymupdf_tables,
        "odl_headings": odl_headings,
        "pymupdf_headings": pymupdf_headings,
        "odl_lists": odl_lists,
        "pymupdf_lists": pymupdf_lists,
        "coverage": cov["coverage"],
        "odl_unique": cov["odl_unique"],
        "pymupdf_unique": cov["pymupdf_unique"],
        "odl_time": odl_time,
        "pymupdf_time": pymupdf_time,
        "odl_garbled": len(odl_garbled),
    })


# ============================================================
print(f"\n\n{'=' * 90}")
print("  FINAL SCORECARD")
print(f"{'=' * 90}")
print(f"\n  {'PDF':<45} {'Text':>7} {'Tables':>7} {'Head':>6} {'Lists':>6} {'Cov':>7} {'Speed':>7}")
print("  " + "-" * 87)

for r in results:
    text_ratio = r["odl_chars"] / max(r["pymupdf_chars"], 1)
    text_s = f"{text_ratio:.2f}x"
    t_s = "+" if r["odl_tables"] > r["pymupdf_tables"] else ("=" if r["odl_tables"] == r["pymupdf_tables"] else "-")
    h_s = "+" if r["odl_headings"] > r["pymupdf_headings"] else ("=" if r["odl_headings"] == r["pymupdf_headings"] else "-")
    l_s = "+" if r["odl_lists"] > r["pymupdf_lists"] else ("=" if r["odl_lists"] == r["pymupdf_lists"] else "-")
    speed = r["pymupdf_time"] / max(r["odl_time"], 0.01)
    print(f"  {r['name']:<45} {text_s:>7} {t_s:>7} {h_s:>6} {l_s:>6} {r['coverage']:>6.1%} {speed:>6.1f}x")

print(f"\n  + = OpenDataLoader better, = = same, - = PyMuPDF better")
print(f"  Text = char ratio (ODL/PyMuPDF), Cov = word vocabulary overlap")
print(f"  Speed = PyMuPDF time / ODL time (PyMuPDF is always faster)")
print()
