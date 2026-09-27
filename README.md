# NEET PG Counselor

A free, static, offline educational website for understanding NEET PG counseling — no server,
no login, no cost to run or host.

## What's in it

- **Guide & Timeline** — plain-language explanation of AIQ vs State Quota, counseling rounds,
  choice locking, reporting/joining, and the usual document checklist.
- **Rank Predictor** — enter rank/category/quota/course-type and see which *kind* of seat
  (tier + course + round) has historically been in reach. Starts from a small **synthetic**
  baseline dataset (`data.js`) — not real MCC/state cutoffs — and self-calibrates from feedback
  (see below).
- **Reservation & Eligibility Calculator** — AIQ reservation percentages (fixed by GoI policy),
  EWS income-threshold check, PwD and In-Service notes. State quota rules vary by state and are
  intentionally not modeled with fake numbers.
- **Ask the Counselor** — an offline, rule-based FAQ chatbot (keyword matching against `data.js`'s
  `FAQS` list). No internet connection or AI model involved.
- **Feedback & Calibration** — the self-improvement loop, see below.

## How the self-improvement loop works

There is no backend, so "self-improving" here means two honest, concrete things rather than one
implied magic thing:

1. **Per-device, live:** every "actual result" you log in the Feedback tab is stored in
   `localStorage` and immediately blended into that bucket's (`quota`/`tier`/`courseType`/
   `category`/`round`) predicted closing rank — more reports in a bucket (up to 5) shift the
   prediction further from the synthetic baseline toward your logged reality.
2. **Across releases, manually:** there's no live sync between users. Use **Export my feedback**
   in the Feedback tab, send the maintainer the JSON file, and it can be appended to
   `calibration-data.js`'s `BUNDLED_CALIBRATION` array in a future commit — so the *shipped*
   baseline improves over time as more real reports accumulate.

The Feedback tab also shows a **leave-one-out self-reported accuracy** number: for every logged
report, it recalculates the prediction using every *other* report (so it's not just grading its
own homework) and checks whether that prediction would have matched the real outcome. With few
reports this number will swing wildly — that's disclosed in the UI, not hidden.

## Running it

No build step. Open `index.html` directly in a browser, or serve the folder with any static
server, e.g.:

```
python3 -m http.server 8000
```

then visit `http://localhost:8000`.

## Important limitations

- Rank Predictor data is **illustrative sample data**, not real published cutoffs. It exists to
  show the shape of how counseling patterns typically look (govt clinical < para-clinical <
  diploma < deemed/private, in terms of closing rank), and to give the self-calibration feature
  something real to attach to once you log actual outcomes.
- Reservation percentages, EWS/PwD criteria, and process descriptions reflect commonly known,
  stable public rules — but eligibility criteria, fees, bonds, and exact round names/rules change
  year to year and vary by state. Always confirm against the official MCC and your state
  counseling authority's current information bulletin before making decisions.
- This project is not affiliated with MCC, NBEMS, or any state counseling authority.
