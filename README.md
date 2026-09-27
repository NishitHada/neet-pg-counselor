# NEET PG Counselor

A free, static, offline educational website for understanding NEET PG counseling — no server,
no login, no cost to run or host.

## What's in it

- **Guide & Timeline** — plain-language explanation of AIQ vs State Quota, counseling rounds,
  choice locking, reporting/joining, and the usual document checklist.
- **Rank Predictor** — enter rank, category, PwD status, quota, program, specialty, state and year.
  It lists every seat (institute + course + quota) that went to someone ranked at or worse than
  you, with that year's closing rank in every round. Built on **262,760 real allotments** parsed
  from MCC's official Final Result PDFs, 2021–2025.
- **Cutoff Explorer** — query the full closing-rank table (year, round, institute, course, quota,
  category, PwD) with CSV export. Each row links to the MCC PDF it came from.
- **Reservation & Eligibility Calculator** — AIQ reservation percentages (fixed by GoI policy),
  EWS income-threshold check, PwD and In-Service notes. State quota rules vary by state and are
  intentionally not modeled with fake numbers.
- **Ask the Counselor** — an offline, rule-based FAQ chatbot (keyword matching against `data.js`'s
  `FAQS` list). No internet connection or AI model involved.

## The data pipeline (`pipeline/`)

MCC publishes each counseling round as a PDF that lists every allotment. Those PDFs are
scattered across the current page and the archive, and their layouts are **not uniform**. At
least seven table layouts exist between 2021 and 2025: some have serial numbers and some don't;
2021 Round 1 carries roll numbers; upgrade rounds (Round 2 and 3) repeat the previous round's seat
in one or two extra column blocks, with padding columns and, in 2025 Round 3, course *codes*; and
quota and category values appear as either full names or abbreviations ("All India"/"AI",
"OBC"/"BC"/"BCNO"). Cells wrap mid-word ("OPHTHALMOLOG⏎Y"), and one institute can appear under up
to 18 spellings.

```
pip install -r pipeline/requirements.txt
python3 pipeline/fetch.py       # downloads the 22 PDFs listed in pipeline/sources.json -> pipeline/raw/
python3 pipeline/extract.py     # header-driven table extraction -> pipeline/extracted/*.jsonl  (~10 min, parallel)
python3 pipeline/normalize.py   # clean + canonicalize -> data/neet_pg.sqlite, data/cutoffs.js, pipeline/report.txt
```

- **extract.py** maps each page's header row by column name and takes the *last*
  quota/institute/course block, which is the seat held after that round. It never reads roll numbers.
- **normalize.py** canonicalizes quotas, categories (with PwD), 391 course spellings (reduced to
  program × specialty), and 12,363 institute spellings (reduced to about 1,980 institutes). It
  clusters institutes by PIN code + name, attaches PIN-less short names to a unique match, and merges
  the same name + city + state listed under two PINs. It keeps only rows where the candidate was
  allotted a seat *in that round* ("Fresh Allotted"/"Upgraded", not "No Upgradation").
- **report.txt** accounts for every raw row: how many were kept, dropped, merged or left
  unresolved, and why.

Sanity checks: no rank repeats within any round, and 60 of 60 randomly sampled DB rows were found
on their cited PDF page.

`data/neet_pg.sqlite` has `sources`, `institutes`, `courses` and `allotments` tables (one row per
allotted candidate), plus a `closing_ranks` view:

```sql
SELECT year, round, institute, city, closing_rank FROM closing_ranks
WHERE specialty = 'Radio-Diagnosis' AND quota = 'All India' AND category = 'Open' AND pwd = 0
ORDER BY year, closing_rank;
```

To add a new round, append its Final Result PDF to `pipeline/sources.json` and re-run the
three steps.

## Running it

No build step. Open `index.html` directly in a browser, or serve the folder with any static
server, e.g.:

```
python3 -m http.server 8000
```

then visit `http://localhost:8000`.

## Important limitations

- Coverage is **MCC counseling only**: AIQ, Deemed/Paid, Central/Delhi/IP/BHU/AMU university,
  NRI, minority and DNB quotas. State-quota counseling (the other 50% of government seats) runs on
  each state's own portal in its own format and isn't included yet.
- "Closing rank" means the worst rank allotted a seat group *in that round*. It is not a seat-matrix
  cutoff, and it moves year to year with seat counts and candidate numbers.
- About 180 institute names appear in the PDFs with no PIN and an ambiguous name (e.g. a bare
  "District Hospital"). These are kept as their own entries without a state rather than guessed;
  see `pipeline/report.txt`.
- Armed Forces seats are ranked by AFMS merit, so the predictor excludes them. They remain in the
  database.
- Reservation percentages, EWS/PwD criteria, and process descriptions reflect commonly known,
  stable public rules — but eligibility criteria, fees, bonds, and exact round names/rules change
  year to year and vary by state. Always confirm against the official MCC and your state
  counseling authority's current information bulletin before making decisions.
- This project is not affiliated with MCC, NBEMS, or any state counseling authority.
