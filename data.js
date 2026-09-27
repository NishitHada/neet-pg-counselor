/*
 * SAMPLE / ILLUSTRATIVE DATA ONLY.
 * Colleges below are generic archetypes (not real named institutions) and closing
 * ranks are synthetically generated to reflect typical shape (govt clinical seats
 * close lower, diploma/deemed seats close higher). This is NOT real MCC or state
 * counseling cutoff data. Always verify against official sources.
 */

const CATEGORY_FACTOR = {
  "UR": 1,
  "EWS": 1.15,
  "OBC-NCL": 1.35,
  "SC": 2.4,
  "ST": 3.1
};

const PWD_FACTOR = 1.6;

const ROUND_FACTOR = {
  "Round 1": 1,
  "Round 2": 1.12,
  "Mop-Up": 1.28,
  "Stray Vacancy": 1.5
};

const COLLEGES = [
  { name: "Govt Medical College (Sample A) — Metro Zone",        tier: "Government",       quota: "AIQ" },
  { name: "Govt Medical College (Sample B) — State Capital",      tier: "Government",       quota: "State Quota" },
  { name: "Central Institute (Sample C)",                         tier: "Government (Central)", quota: "AIQ" },
  { name: "State Medical College (Sample D) — Tier-2 City",       tier: "Government",       quota: "State Quota" },
  { name: "Deemed University Medical College (Sample E)",         tier: "Deemed/Private",   quota: "AIQ" },
  { name: "Private Medical College (Sample F)",                   tier: "Private",          quota: "State Quota" }
];

const COURSES = [
  { name: "MD General Medicine",      type: "Clinical",                    baseRank: 1200 },
  { name: "MS General Surgery",       type: "Clinical",                    baseRank: 1800 },
  { name: "MD Radio-Diagnosis",       type: "Clinical",                    baseRank: 2500 },
  { name: "MD Pediatrics",            type: "Clinical",                    baseRank: 3200 },
  { name: "MD Anatomy",               type: "Para-clinical/Pre-clinical",  baseRank: 9000 },
  { name: "MD Community Medicine",    type: "Para-clinical/Pre-clinical",  baseRank: 11000 },
  { name: "Diploma in Child Health",  type: "Diploma",                     baseRank: 22000 }
];

const TIER_FACTOR = {
  "Government": 1,
  "Government (Central)": 0.7,
  "Deemed/Private": 4.5,
  "Private": 5.5
};

function buildDataset() {
  const rows = [];
  let seed = 7;
  function pseudoRandom() {
    seed = (seed * 9301 + 49297) % 233280;
    return seed / 233280;
  }

  COLLEGES.forEach(college => {
    COURSES.forEach(course => {
      Object.keys(ROUND_FACTOR).forEach(round => {
        const jitter = 0.85 + pseudoRandom() * 0.3;
        const closingRank = Math.round(
          course.baseRank * TIER_FACTOR[college.tier] * ROUND_FACTOR[round] * jitter
        );
        rows.push({
          college: college.name,
          tier: college.tier,
          quota: college.quota,
          course: course.name,
          courseType: course.type,
          round: round,
          urClosingRank: closingRank
        });
      });
    });
  });
  return rows;
}

const DATASET = buildDataset();

function estimateClosingRank(urClosingRank, category, isPwd) {
  let factor = CATEGORY_FACTOR[category] || 1;
  if (isPwd) factor *= PWD_FACTOR;
  return Math.round(urClosingRank * factor);
}

const FAQS = [
  {
    q: "what is aiq all india quota",
    keywords: ["aiq", "all india quota"],
    a: "AIQ (All India Quota) covers 50% of government MD/MS/Diploma seats surrendered by states to a central pool, plus all deemed/private university and central institute seats. It's conducted by MCC, and any eligible NEET PG candidate from any state can apply."
  },
  {
    q: "what is state quota",
    keywords: ["state quota"],
    a: "State Quota covers the remaining 50% of government seats plus state-run private college seats. Each state runs its own counseling with its own reservation rules, domicile requirements, and timeline — separate from MCC's AIQ counseling."
  },
  {
    q: "what is stray vacancy round",
    keywords: ["stray vacancy", "stray round"],
    a: "The Stray Vacancy round fills seats still empty after Mop-Up. It's usually the last round, often has compressed timelines, and rules on withdrawal or re-registration tend to be stricter — check that year's bulletin carefully."
  },
  {
    q: "what is mop up round",
    keywords: ["mop-up", "mop up"],
    a: "Mop-Up is typically the round after Round 2, used to fill vacancies created by candidates upgrading, withdrawing, or not joining. New candidates can also register if eligible."
  },
  {
    q: "choice locking meaning",
    keywords: ["choice lock", "lock choices", "choice filling"],
    a: "Choice locking means confirming your ranked list of college+course preferences before a deadline. Depending on the year's rules, an unlocked list may be auto-locked as-is or may not be considered at all — always lock manually if the option exists."
  },
  {
    q: "ews income limit criteria",
    keywords: ["ews income", "ews criteria", "ews limit"],
    a: "EWS (Economically Weaker Section) reservation generally requires annual family income below a government-notified threshold (commonly cited as ₹8 lakh) and limits on land/property holdings, along with not belonging to any other reserved category. Exact current criteria should be confirmed from the official EWS certificate notification for that year."
  },
  {
    q: "pwd reservation criteria",
    keywords: ["pwd", "disability reservation", "pwbd"],
    a: "PwD (Persons with Disability) reservation is typically a horizontal reservation of around 5% under AIQ, applicable across all categories, for candidates with a benchmark disability of 40% or more as certified by an authorized medical board."
  },
  {
    q: "in service quota",
    keywords: ["in-service", "in service quota"],
    a: "In-Service quota is reserved for doctors already working in a state's government health department, usually under state quota counseling, with its own eligibility rules (years of rural/government service, etc.) set by that state."
  },
  {
    q: "domicile requirement state quota",
    keywords: ["domicile"],
    a: "State Quota counseling usually requires proof of domicile in that state (e.g. based on schooling, residence, or parental domicile — rules vary by state). AIQ has no domicile requirement."
  },
  {
    q: "category certificate validity",
    keywords: ["category certificate", "certificate validity"],
    a: "Category certificates (OBC-NCL, SC, ST, EWS, PwD) are generally required to be valid/issued for the specific counseling year — an outdated certificate (e.g. from a previous year, for OBC-NCL/EWS which need annual renewal) may be rejected during verification."
  },
  {
    q: "seat upgradation meaning",
    keywords: ["upgradation", "upgrade seat"],
    a: "Upgradation means a candidate already allotted a seat gets moved to a higher-preference choice in a later round, based on rank and available vacancies, without needing to re-register."
  },
  {
    q: "what happens if i dont join allotted seat",
    keywords: ["not join", "forfeit", "don't report", "seat forfeiture"],
    a: "Not reporting/joining an allotted seat without valid upgradation intent typically leads to seat forfeiture, loss of counseling fee/security deposit, and in many states a period of debarment from further counseling that year. Rules differ by quota and state, so check the current bulletin."
  },
  {
    q: "md vs ms difference",
    keywords: ["md vs ms", "difference md ms"],
    a: "MD (Doctor of Medicine) covers clinical, para-clinical, and pre-clinical specialties (e.g. General Medicine, Pediatrics, Anatomy). MS (Master of Surgery) covers surgical specialties (e.g. General Surgery, Orthopedics, ENT). Both are postgraduate degrees of equal academic standing in their respective streams."
  },
  {
    q: "can i do aiq and state counseling together",
    keywords: ["both aiq and state", "aiq and state together"],
    a: "Yes — AIQ and State Quota counseling run on separate, often overlapping timelines, and you can register for and participate in both, subject to each authority's specific rules about simultaneous participation and seat acceptance."
  },
  {
    q: "security deposit counseling fee",
    keywords: ["security deposit", "counseling fee", "registration fee"],
    a: "Most counseling authorities charge a registration fee and require a refundable security deposit (amounts vary widely by quota/state/category and change periodically) — refund conditions depend on whether you join, upgrade, or withdraw, so check the current fee structure in the official bulletin."
  },
  {
    q: "bond service obligation",
    keywords: ["bond", "service obligation", "rural bond"],
    a: "Some states require a service bond (a fixed period of government/rural service, or a penalty amount if not served) as a condition for certain government seats. Bond duration and penalty amounts vary significantly by state — always check your specific state's rules."
  },
  {
    q: "reservation percentage aiq",
    keywords: ["reservation percentage", "reservation quota percent"],
    a: "Under AIQ, the commonly applied reservation percentages are: OBC-NCL 27%, SC 15%, ST 7.5%, EWS 10%, with PwD as a 5% horizontal reservation cutting across all categories. State quota reservation percentages vary by state."
  },
  {
    q: "rank vs merit position",
    keywords: ["rank vs merit", "merit position"],
    a: "Your NEET PG rank/percentile determines your merit position for counseling. Allotment in each round is based on this merit position matched against your locked choices and seat availability — a better rank gives priority when multiple candidates compete for the same seat."
  },
  {
    q: "documents required reporting",
    keywords: ["documents required", "documents reporting", "document checklist"],
    a: "Commonly required: NEET PG admit card & rank letter, MBBS/BDS degree certificate & mark sheets, internship completion certificate, medical registration certificate, valid category/domicile certificates, photo ID, photographs, and fee/deposit payment receipt. Exact list varies by quota/state."
  },
  {
    q: "fresh vs upgradation candidate",
    keywords: ["fresh candidate", "upgradation candidate"],
    a: "A 'fresh' candidate is someone not yet allotted any seat in that counseling process, while an 'upgradation' candidate already holds a seat and is trying to move to a higher preference. Some rounds treat these two groups differently in terms of eligibility or priority."
  }
];
