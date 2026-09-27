"""Stage 2: turn extracted/*.jsonl into one clean, queryable database.

Outputs
  data/neet_pg.sqlite  - full normalized DB (sources, institutes, courses, allotments + closing_ranks view)
  data/cutoffs.js      - compact closing-rank table the static site loads (works from file://)
  pipeline/report.txt  - what got merged, dropped or left unresolved, so nothing is silent

Only rows where the candidate holds a seat in THIS round's result are kept as allotments
(simple layouts: every row; upgrade layouts: "Fresh Allotted" / "Upgraded" rows). Rows that say
"No Upgradation", "Did not opt", "Not Allotted" carry no new seat and are counted in the report.
"""
import collections, json, pathlib, re, sqlite3

HERE = pathlib.Path(__file__).parent
ROOT = HERE.parent
DATA = ROOT / "data"


def alnum(s):
    return re.sub(r"[^A-Z0-9]", "", (s or "").upper())


def oneline(s):
    return re.sub(r"\s+", " ", (s or "").replace("\n", " ")).strip(" ,")


# ---------------------------------------------------------------- quotas & categories
QUOTAS = {  # alnum key or abbreviation -> canonical label
    "ALLINDIA": "All India", "AI": "All India",
    "DNBQUOTA": "DNB", "AD": "DNB",
    "MANAGEMENTPAIDSEATSQUOTA": "Deemed/Paid", "PS": "Deemed/Paid",
    "SELFFINANCEDMERITSEATPAIDSEATQUOTA": "Deemed/Paid", "SELFFINANCEDMERITSEAT": "Deemed/Paid",
    "NONRESIDENTINDIAN": "NRI", "NR": "NRI",
    "DELHIUNIVERSITYQUOTA": "Delhi University", "DELHIUNIVERSITIES": "Delhi University", "DU": "Delhi University",
    "IPUNIVERSITYQUOTA": "IP University", "IP": "IP University",
    "ALIGARHMUSLIMUNIVERSITY": "Aligarh Muslim University", "AM": "Aligarh Muslim University",
    "BANARASHINDUUNIVERSITY": "Banaras Hindu University", "BH": "Banaras Hindu University",
    "JAINMINORITYQUOTA": "Jain Minority", "JM": "Jain Minority",
    "MUSLIMMINORITYQUOTA": "Muslim Minority", "MM": "Muslim Minority",
    "ARMEDFORCESMEDICAL": "Armed Forces", "AF": "Armed Forces",
    "INTERNALQUOTA": "Internal", "IQ": "Internal",
    "OPENSEATQUOTA": "Open Seat", "SO": "Open Seat",
}

CATEGORY = {"OPEN": "Open", "OP": "Open", "GN": "Open", "GENERAL": "Open",
            "OBC": "OBC", "BC": "OBC", "EWS": "EWS", "EW": "EWS", "SC": "SC", "ST": "ST"}


def parse_category(raw):
    """'Open PwD' / 'OBC' / 'OPNO' / 'BCPH' / 'GNYes' -> (category, pwd)."""
    k = alnum(raw)
    pwd = k.endswith("PWD") or k.endswith("PH") or k.endswith("YES")
    k = re.sub(r"(PWD|PH|NO|YES)$", "", k)
    return CATEGORY.get(k), pwd


# ---------------------------------------------------------------- courses
PROGRAMS = [  # (program, test on alnum key)
    ("DNB Diploma", lambda k: k.startswith("NBEMSDIPLOMA")),
    ("DNB", lambda k: k.startswith("NBEMS")),
    ("Diploma", lambda k: k.startswith("DIP") or k.startswith("PGDIPLOMA")),
    ("M.Ch", lambda k: k.startswith("MCH")),
    ("MPH", lambda k: k.startswith("MPH")),
    ("MD/MS", lambda k: k.startswith("MD") or k.startswith("MS")),
]

SPECIALTIES = [  # first match wins; tested against alnum key with the program prefix stripped
    ("Anaesthesiology", r"ANAESTH"),
    ("Radio-Diagnosis", r"RADIODIAGNOSIS"),
    ("Radiation Oncology", r"RADIOTHERAPY|RADIATIONONCOLOGY|MEDICALRADIOTHERAPY"),
    ("Radiation Medicine", r"RADIATIONMEDICINE"),
    ("General Medicine", r"^GENERALMEDICINE"),
    ("General Surgery", r"^GENERALSURGERY"),
    ("Obstetrics & Gynaecology", r"OBST|GYNAE"),
    ("Paediatric Surgery", r"PAEDIATRICSURGERY"),
    ("Paediatrics", r"PAEDIATRIC|CHILDHEALTH"),
    ("Orthopaedics", r"ORTHOPAEDIC"),
    ("Ophthalmology", r"OPHTHALMOLOGY"),
    ("ENT", r"ENT$|OTORHINO"),
    ("Dermatology", r"DERM"),
    ("Psychiatry", r"PSYCH"),
    ("Respiratory Medicine", r"TUBERCULOSIS|RESPIRATORY|TBANDCHEST"),
    ("Emergency Medicine", r"EMERGENCY"),
    ("Family Medicine", r"FAMILYMEDICINE"),
    ("Geriatrics", r"GERIATRIC"),
    ("Palliative Medicine", r"PALLIATIVE"),
    ("Nuclear Medicine", r"NUCLEARMEDICINE"),
    ("Physical Medicine & Rehabilitation", r"PHYMEDICINE|PHYSICALMED"),
    ("Sports Medicine", r"SPORTSMEDICINE"),
    ("Transfusion Medicine", r"TRANSFUSION|IMMUNOHAEMATOLOGY"),
    ("Pathology", r"PATHOLOGY|LABORATORYMEDICINE"),
    ("Microbiology", r"MICROBIOLOGY|BACTERIOLOGY"),
    ("Pharmacology", r"PHARMACOLOGY"),
    ("Physiology", r"PHYSIOLOGY"),
    ("Biochemistry", r"BIOCHEMISTRY"),
    ("Anatomy", r"ANATOMY"),
    ("Forensic Medicine", r"FORENSIC"),
    ("Community Medicine", r"COMMUNITY|PREVENTIVE|PUBLICHEALTH|EPIDEMIOLOGY"),
    ("Hospital Administration", r"HOSPITALADMIN|HEALTHADMIN"),
    ("Tropical Medicine", r"TROPICAL"),
    ("Aerospace Medicine", r"AEROSPACE"),
    ("Diabetology", r"DIABETOLOGY"),
    ("Traumatology & Surgery", r"TRAUMATOLOGY"),
    ("Cardiothoracic Surgery", r"CARDIOVASCULAR"),
    ("Neurosurgery", r"NEUROSURGERY"),
    ("Plastic Surgery", r"PLASTIC"),
]

CLINICAL = {"Anatomy", "Physiology", "Biochemistry"}  # pre-clinical
PARA = {"Pathology", "Microbiology", "Pharmacology", "Forensic Medicine", "Community Medicine",
        "Transfusion Medicine", "Hospital Administration"}


def classify_course(raw):
    k = alnum(raw)
    program = next((p for p, test in PROGRAMS if test(k)), None)
    body = re.sub(r"^(NBEMSDIPLOMA|NBEMS|PGDIPLOMAIN|DIPLOMAIN|DIPIN|DIPLOMA|DIP|MDMS|MPH|MCH|MD|MS)(IN)?", "", k)
    specialty = next((name for name, rx in SPECIALTIES if re.search(rx, body)), None)
    if specialty is None:
        return program, None, None
    branch = ("Pre-clinical" if specialty in CLINICAL else
              "Para-clinical" if specialty in PARA else "Clinical")
    return program, specialty, branch


# ---------------------------------------------------------------- institutes
STATES = {
    "Andaman and Nicobar Islands": ["ANDAMANANDNICOBAR", "ANDAMAN"],
    "Andhra Pradesh": ["ANDHRAPRADESH"], "Arunachal Pradesh": ["ARUNACHALPRADESH"],
    "Assam": ["ASSAM"], "Bihar": ["BIHAR"], "Chandigarh": ["CHANDIGARH"],
    "Chhattisgarh": ["CHHATTISGARH", "CHATTISGARH"],
    "Dadra and Nagar Haveli and Daman and Diu": ["DADRAANDNAGARHAVELI", "DAMANANDDIU"],
    "Delhi": ["DELHINCT", "NEWDELHI", "DELHI"], "Goa": ["GOA"], "Gujarat": ["GUJARAT"],
    "Haryana": ["HARYANA"], "Himachal Pradesh": ["HIMACHALPRADESH"],
    "Jammu and Kashmir": ["JAMMUANDKASHMIR", "JAMMUKASHMIR"], "Jharkhand": ["JHARKHAND"],
    "Karnataka": ["KARNATAKA"], "Kerala": ["KERALA"], "Ladakh": ["LADAKH"],
    "Madhya Pradesh": ["MADHYAPRADESH"], "Maharashtra": ["MAHARASHTRA"], "Manipur": ["MANIPUR"],
    "Meghalaya": ["MEGHALAYA"], "Mizoram": ["MIZORAM"], "Nagaland": ["NAGALAND"],
    "Odisha": ["ODISHA", "ORISSA"], "Puducherry": ["PUDUCHERRY", "PONDICHERRY"],
    "Punjab": ["PUNJAB"], "Rajasthan": ["RAJASTHAN"], "Sikkim": ["SIKKIM"],
    "Tamil Nadu": ["TAMILNADU"], "Telangana": ["TELANGANA"], "Tripura": ["TRIPURA"],
    "Uttar Pradesh": ["UTTARPRADESH"], "Uttarakhand": ["UTTARAKHAND", "UTTRAKHAND"],
    "West Bengal": ["WESTBENGAL"],
}
# Indian PIN codes: first two digits identify the postal circle, which disambiguates a missing state.
PIN_STATE = [((11, 11), "Delhi"), ((12, 13), "Haryana"), ((14, 15), "Punjab"), ((16, 16), "Chandigarh"),
             ((17, 17), "Himachal Pradesh"), ((18, 19), "Jammu and Kashmir"), ((20, 28), "Uttar Pradesh"),
             ((30, 34), "Rajasthan"), ((36, 39), "Gujarat"), ((40, 44), "Maharashtra"), ((45, 48), "Madhya Pradesh"),
             ((49, 49), "Chhattisgarh"), ((50, 50), "Telangana"), ((51, 53), "Andhra Pradesh"),
             ((56, 59), "Karnataka"), ((60, 64), "Tamil Nadu"), ((67, 69), "Kerala"), ((70, 74), "West Bengal"),
             ((75, 77), "Odisha"), ((78, 78), "Assam"), ((79, 79), "Northeast"), ((80, 85), "Bihar")]


def pin_of(raw):
    pins = re.findall(r"(?<!\d)(\d{6})(?!\d)", (raw or "").replace("\n", ""))
    return pins[-1] if pins else None


def state_of(raw, pin):
    k = alnum(raw)
    best = None
    for state, keys in STATES.items():
        for key in keys:
            pos = k.rfind(key)
            if pos >= 0 and (best is None or pos > best[0]):
                best = (pos, state)
    if best:
        return best[1]
    if pin:
        p = int(pin[:2])
        return next((s for (lo, hi), s in PIN_STATE if lo <= p <= hi), None)
    return None


def city_of(raw, name, state):
    """Best-effort city: the last short, alphabetic address segment that isn't the name, state or PIN."""
    skip = {alnum(name), alnum(state or "")} | {alnum(k) for k in STATES.get(state, [])}
    for seg in reversed([oneline(x) for x in re.split(r",", raw)]):
        seg = re.sub(r"[-\s]*\d{3}\s?\d{3}$", "", seg).strip(" .-")
        k = alnum(seg)
        if (3 <= len(seg) <= 25 and k and k not in skip and not re.search(r"\d", seg)
                and not re.search(r"ROAD|MARG|NAGAR|SECTOR|STREET|POST|DIST|OPP|NEAR|SALAI|COLONY|BLOCK|LANE|CHOWK|AREA|\bPO\b", seg.upper())
                and not any(k in v for v in skip if v)):
            return seg.title() if seg.isupper() else seg
    return None


def head_of(raw):
    """Institution name = text before the first comma (the rest is address). Empty-field
    artefacts like 'Name, ,Address' and 'Name ,' are handled by the same split."""
    first = re.split(r"\s*,", raw, maxsplit=1)[0]
    return oneline(first)


# ---------------------------------------------------------------- build
def main():
    sources = json.loads((HERE / "sources.json").read_text())
    DATA.mkdir(exist_ok=True)
    report = collections.defaultdict(collections.Counter)

    rows = []
    for sid, src in enumerate(sources["sources"], 1):
        path = HERE / "extracted" / f"{src['year']}_{src['round'].lower().replace(' ', '-')}.jsonl"
        src["id"], src["url"], src["n_raw"] = sid, sources["base"] + src["path"], 0
        for line in path.open():
            r = json.loads(line)
            src["n_raw"] += 1
            if r["institute"] in (None, "", "-"):
                report["no seat in this round (by remark)"][oneline(re.sub(r"\(.*", "", r["remarks"] or ""))] += 1
                continue
            r["source"] = sid
            rows.append(r)

    # --- institutes
    # 1. Entries with a PIN cluster by (PIN, name head); heads at the same PIN merge when one is a
    #    prefix of the other (wrapped/truncated spellings).
    # 2. PIN-less entries (upgrade layouts often print just "Name" or "Name, City") attach to a
    #    unique match: exact head, then full-string prefix, then head prefix; ties broken by state.
    # 3. Clusters with the same head, state and city merge (same institute listed under two PINs).
    clusters = {}  # key -> {"variants": Counter(raw -> rows), "pin": str|None}
    raw_to_cluster = {}
    by_head = collections.defaultdict(set)
    for raw in sorted({r["institute"] for r in rows}, key=lambda s: -len(s)):
        pin, hk = pin_of(raw), alnum(head_of(raw))
        if not pin:
            continue
        key = next((k for k in clusters if k[0] == pin and (k[1].startswith(hk) or hk.startswith(k[1]))), (pin, hk))
        clusters.setdefault(key, {"pin": pin})
        raw_to_cluster[raw] = key
        by_head[hk].add(key)
    full_keys = collections.defaultdict(set)
    for raw, key in raw_to_cluster.items():
        full_keys[alnum(raw)].add(key)
    cluster_state = {}
    for raw, key in raw_to_cluster.items():
        cluster_state.setdefault(key, collections.Counter())[state_of(raw, key[0])] += 1
    cluster_state = {k: c.most_common(1)[0][0] for k, c in cluster_state.items()}

    for raw in sorted({r["institute"] for r in rows} - raw_to_cluster.keys()):
        fk, hk, st = alnum(raw), alnum(head_of(raw)), state_of(raw, None)
        cands = set()
        for finder in (lambda: by_head.get(hk, set()),
                       lambda: {k for f, ks in full_keys.items() if f.startswith(fk) for k in ks} if len(fk) >= 8 else set(),
                       lambda: {k for h, ks in by_head.items() if h.startswith(hk) or hk.startswith(h) for k in ks} if len(hk) >= 8 else set()):
            cands = set(finder())
            if len(cands) > 1 and st:
                cands = {k for k in cands if cluster_state.get(k) == st} or cands
            if len(cands) == 1:
                break
        if len(cands) == 1:
            raw_to_cluster[raw] = cands.pop()
            report["institutes"]["PIN-less name attached to a unique full entry"] += 1
        else:
            raw_to_cluster[raw] = (None, hk)
            clusters.setdefault((None, hk), {"pin": None})
            report["institutes"]["PIN-less name, ambiguous or unmatched (kept as its own institute)"] += 1

    for c in clusters.values():
        c["variants"] = collections.Counter()
    for r in rows:
        clusters[raw_to_cluster[r["institute"]]]["variants"][r["institute"]] += 1

    def describe(c):
        # display name: the head spelled with the fewest line breaks (wide columns => no mid-word wraps)
        best = min(c["variants"], key=lambda v: (v.split(",")[0].count("\n"), -c["variants"][v]))
        full = max(c["variants"], key=lambda v: (bool(pin_of(v)), c["variants"][v], -v.count("\n")))
        states = collections.Counter()
        for v, n in c["variants"].items():
            states[state_of(v, c["pin"])] += n
        states.pop(None, None)
        state = states.most_common(1)[0][0] if states else None
        name = head_of(best)
        if len(name) < 12:  # bare acronyms like "PGIMER": keep the next segment ("PGIMER, DR. RML Hospital")
            name = ", ".join(re.split(r"\s*,\s*", oneline(best))[:2])
        return {"name": name, "state": state, "city": city_of(full, name, state), "pin": c["pin"], "address": oneline(full)}

    merged = {}
    for key, c in clusters.items():
        d = describe(c)
        mkey = (alnum(d["name"]), d["state"], alnum(d["city"])) if d["city"] and d["state"] else key
        if mkey in merged:
            merged[mkey]["variants"].update(c["variants"])
            report["institutes"]["same name+city+state under a second PIN (merged)"] += 1
        else:
            merged[mkey] = c
        for raw in c["variants"]:
            raw_to_cluster[raw] = mkey

    inst_ids, institutes = {}, []
    for key, c in merged.items():
        d = describe(c)
        inst_ids[key] = len(institutes) + 1
        institutes.append({"id": len(institutes) + 1, **d, "n_variants": len(c["variants"])})

    # --- courses
    course_ids, courses = {}, []
    for raw in sorted({r["course"] for r in rows}):
        program, specialty, branch = classify_course(raw)
        k = (program, specialty)
        if specialty is None:
            report["courses: unclassified (kept as-is)"][oneline(raw)] += 1
            k = (program, oneline(raw))
        if k not in course_ids:
            course_ids[k] = len(courses) + 1
            courses.append({"id": len(courses) + 1, "program": program, "specialty": k[1], "branch": branch,
                            "name": f"{program} {k[1]}" if program else k[1]})
        course_ids[raw] = course_ids[k]

    # --- allotments
    allot = []
    for r in rows:
        quota = QUOTAS.get(alnum(r["quota"]))
        if not quota:
            report["quota: unknown (row dropped)"][oneline(r["quota"])] += 1
            continue
        cat, pwd = parse_category(r["allotted_cat"])
        if cat is None:
            report["allotted category: unknown (row dropped)"][oneline(r["allotted_cat"])] += 1
            continue
        ccat, cpwd = parse_category(r["candidate_cat"]) if r["candidate_cat"] not in (None, "-") else (None, None)
        allot.append((r["source"], r["rank"], quota, inst_ids[raw_to_cluster[r["institute"]]], course_ids[r["course"]],
                      cat, int(pwd), ccat, None if cpwd is None else int(cpwd), oneline(r["remarks"]) or None, r["page"]))

    # --- SQLite
    db_path = DATA / "neet_pg.sqlite"
    db_path.unlink(missing_ok=True)
    db = sqlite3.connect(db_path)
    db.executescript("""
    CREATE TABLE sources (id INTEGER PRIMARY KEY, year INT, round TEXT, title TEXT, url TEXT, raw_rows INT, allotments INT);
    CREATE TABLE institutes (id INTEGER PRIMARY KEY, name TEXT, city TEXT, state TEXT, pin TEXT, address TEXT, n_variants INT);
    CREATE TABLE courses (id INTEGER PRIMARY KEY, name TEXT, program TEXT, specialty TEXT, branch TEXT);
    CREATE TABLE allotments (
      source_id INT REFERENCES sources, rank INT, quota TEXT, institute_id INT REFERENCES institutes,
      course_id INT REFERENCES courses, allotted_category TEXT, allotted_pwd INT,
      candidate_category TEXT, candidate_pwd INT, remarks TEXT, pdf_page INT);
    CREATE INDEX ix_allot ON allotments (institute_id, course_id, quota, allotted_category, allotted_pwd);
    CREATE VIEW closing_ranks AS
      SELECT s.year, s.round, a.quota, i.name AS institute, i.city, i.state, c.name AS course, c.program, c.specialty,
             a.allotted_category AS category, a.allotted_pwd AS pwd,
             MIN(a.rank) AS opening_rank, MAX(a.rank) AS closing_rank, COUNT(*) AS seats_allotted
      FROM allotments a JOIN sources s ON s.id = a.source_id
      JOIN institutes i ON i.id = a.institute_id JOIN courses c ON c.id = a.course_id
      GROUP BY s.id, a.quota, a.institute_id, a.course_id, a.allotted_category, a.allotted_pwd;
    """)
    per_source = collections.Counter(a[0] for a in allot)
    db.executemany("INSERT INTO sources VALUES (?,?,?,?,?,?,?)",
                   [(s["id"], s["year"], s["round"], s["title"], s["url"], s["n_raw"], per_source[s["id"]]) for s in sources["sources"]])
    db.executemany("INSERT INTO institutes VALUES (:id,:name,:city,:state,:pin,:address,:n_variants)", institutes)
    db.executemany("INSERT INTO courses VALUES (:id,:name,:program,:specialty,:branch)", courses)
    db.executemany("INSERT INTO allotments VALUES (?,?,?,?,?,?,?,?,?,?,?)", allot)
    db.commit()

    # --- compact closing-rank table for the static site
    grouped = db.execute("""
      SELECT a.source_id, a.quota, a.institute_id, a.course_id, a.allotted_category, a.allotted_pwd,
             MIN(a.rank), MAX(a.rank), COUNT(*)
      FROM allotments a GROUP BY 1,2,3,4,5,6""").fetchall()
    quotas = sorted({g[1] for g in grouped})
    cats = ["Open", "EWS", "OBC", "SC", "ST"]
    site = {
        "generated_from": "MCC (mcc.nic.in) Final Result PDFs — see pipeline/sources.json",
        "sources": [{"id": s["id"], "year": s["year"], "round": s["round"], "url": s["url"]} for s in sources["sources"]],
        "quotas": quotas, "categories": cats,
        "institutes": [[i["name"], i["city"], i["state"]] for i in institutes],
        "courses": [[c["name"], c["program"], c["specialty"], c["branch"]] for c in courses],
        # [source_id, quota_idx, institute_idx, course_idx, category_idx, pwd, opening, closing, seats]
        "rows": [[g[0], quotas.index(g[1]), g[2] - 1, g[3] - 1, cats.index(g[4]), g[5], g[6], g[7], g[8]] for g in grouped],
    }
    (DATA / "cutoffs.js").write_text("/* Generated by pipeline/normalize.py — do not edit by hand. */\nconst CUTOFFS = "
                                     + json.dumps(site, separators=(",", ":"), ensure_ascii=False) + ";\n")

    # --- report
    with (HERE / "report.txt").open("w") as fh:
        fh.write(f"raw rows: {sum(s['n_raw'] for s in sources['sources'])}\nallotments kept: {len(allot)}\n"
                 f"institutes: {len(institutes)} (from {len({r['institute'] for r in rows})} raw spellings)\n"
                 f"courses: {len(courses)} (from {len({r['course'] for r in rows})} raw spellings)\n"
                 f"closing-rank groups: {len(grouped)}\n\n")
        for s in sources["sources"]:
            fh.write(f"  {s['year']} {s['round']:<14} raw {s['n_raw']:>6}  allotments {per_source[s['id']]:>6}\n")
        for section, counts in report.items():
            fh.write(f"\n[{section}]\n")
            for k, v in counts.most_common():
                fh.write(f"  {v:>7}  {k}\n")
    print((HERE / "report.txt").read_text())


if __name__ == "__main__":
    main()
