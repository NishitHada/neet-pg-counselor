"""Stage 1: pull raw allotment rows out of every MCC result PDF into pipeline/extracted/*.jsonl.

MCC has used at least seven different table layouts across 2021-2025:
  * simple:   SNo | Rank | Quota | Institute | Course | Allotted Cat | Candidate Cat | Remarks
  * 2021 R1:  S.No | Roll No | Rank | Quota | Institute | Course | Allotted Cat | Candidate Cat
  * upgrade:  [SNo] | Rank | <one or two previous-round blocks: Quota | Institute | Course | Remarks>
              | Quota | Institute | Course | Allotted Cat | Candidate Cat | Option No | Remarks
    with stray None padding columns and, in 2025 R3, course *codes* in the earlier blocks.
Rather than hardcode per-file layouts, each page's header row is mapped by name, and for the
upgrade layout we take the LAST quota/institute/course block — the seat held after this round.
Roll numbers are never read.
"""
import json, pathlib, re, sys
from multiprocessing import Pool

import pdfplumber

HERE = pathlib.Path(__file__).parent
RAW, OUT = HERE / "raw", HERE / "extracted"
CHUNK = 150


def key(cell):
    return re.sub(r"[^a-z]", "", (cell or "").lower())


def map_header(row):
    """Return {row width: {field: column index}} if this row is a header row, else None.

    Some upgrade-format headers carry an empty padding column that the data rows lack, so the
    header is also mapped with its None cells dropped and the row width picks the mapping."""
    full = _map([key(c) for c in row])
    compact = _map([key(c) for c in row if c is not None])
    if not full:
        return None
    return {len(row): full, sum(c is not None for c in row): compact}


def _map(keys):
    if "rank" not in keys:
        return None
    last = lambda pred: max((i for i, k in enumerate(keys) if pred(k)), default=None)
    m = {
        "rank": keys.index("rank"),
        "quota": last(lambda k: k.startswith("allot") and k.endswith("quota")),
        "institute": last(lambda k: k.startswith("allot") and "inst" in k),
        "course": last(lambda k: k == "course"),
        "allotted_cat": last(lambda k: k.startswith("allot") and k.endswith("category")),
        "candidate_cat": last(lambda k: k.startswith("candid")),
        "remarks": last(lambda k: k == "remarks"),
    }
    return m if m["institute"] is not None and m["course"] is not None else None


def clean(cell):
    # Keep line breaks as "\n": PDF cell wrapping splits words mid-token ("OPHTHALMOLOG\nY"),
    # which normalize.py resolves by comparing names with all whitespace removed.
    return "\n".join(re.sub(r"[ \t]+", " ", ln).strip() for ln in (cell or "").strip().splitlines())


def work(job):
    path, start, stop = job
    rows, header, skipped = [], None, 0
    with pdfplumber.open(path) as pdf:
        # Continuation pages may not repeat the header; seed from the first header in the file.
        for pg in pdf.pages[: min(len(pdf.pages), 6)]:
            for r in pg.extract_table() or []:
                header = header or map_header(r)
        for i in range(start, stop):
            for r in (r for t in pdf.pages[i].extract_tables() for r in t):
                h = map_header(r)
                if h:
                    header = h
                    continue
                cols = header.get(len(r))
                if not cols:
                    skipped += bool(r and (r[0] or "").strip().isdigit())
                    continue
                rank = clean(r[cols["rank"]])
                if not rank.isdigit():
                    continue
                rec = {f: (clean(r[ix]) if ix is not None else None) for f, ix in cols.items()}
                rec["rank"] = int(rank)
                rec["page"] = i + 1
                rows.append(rec)
    return path, start, rows, skipped


def main():
    OUT.mkdir(exist_ok=True)
    files = sorted(RAW.glob("*.pdf"))
    if len(sys.argv) > 1:
        files = [f for f in files if any(a in f.name for a in sys.argv[1:])]
    jobs = []
    for f in files:
        with pdfplumber.open(f) as pdf:
            n = len(pdf.pages)
        jobs += [(str(f), s, min(s + CHUNK, n)) for s in range(0, n, CHUNK)]
    results = {}
    with Pool() as pool:
        for path, start, rows, skipped in pool.imap_unordered(work, jobs):
            results.setdefault(path, {})[start] = rows
            if skipped:
                print(f"{pathlib.Path(path).name} p{start}: skipped {skipped} unaligned rows", flush=True)
    for path, chunks in results.items():
        out = OUT / (pathlib.Path(path).stem + ".jsonl")
        with out.open("w") as fh:
            for s in sorted(chunks):
                for rec in chunks[s]:
                    fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
