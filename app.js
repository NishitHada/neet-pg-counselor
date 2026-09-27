/* ---------- Tabs ---------- */
document.querySelectorAll(".tab-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
    document.querySelectorAll(".tab-panel").forEach(p => p.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById(btn.dataset.tab).classList.add("active");
    if (btn.dataset.tab === "feedback") refreshFeedbackUI();
    if (btn.dataset.tab === "predictor") refreshCalibrationStatus();
  });
});

/* ---------- Feedback storage (client-side self-improvement) ---------- */
const FEEDBACK_KEY = "neetpg_counselor_feedback_v1";

function loadLocalFeedback() {
  try {
    return JSON.parse(localStorage.getItem(FEEDBACK_KEY)) || [];
  } catch (e) {
    return [];
  }
}

function saveLocalFeedback(arr) {
  localStorage.setItem(FEEDBACK_KEY, JSON.stringify(arr));
}

function allFeedback() {
  const bundled = (typeof BUNDLED_CALIBRATION !== "undefined" ? BUNDLED_CALIBRATION : [])
    .map(e => ({ ...e, source: e.source || "community" }));
  return bundled.concat(loadLocalFeedback());
}

function bucketKey(entry) {
  return [entry.quota, entry.tier, entry.courseType, entry.category, entry.round].join("|");
}

/* Empirical closing-rank estimate for a bucket from a feedback array,
   using the worst ("got_seat") rank observed as the closing-rank proxy. */
function calibratedRankForBucket(key, feedbackArr) {
  const gotRanks = feedbackArr
    .filter(e => bucketKey(e) === key && e.outcome === "got_seat")
    .map(e => Number(e.rank));
  if (gotRanks.length === 0) return null;
  return { rank: Math.max(...gotRanks), count: gotRanks.length };
}

function blend(baseline, calibrated) {
  if (!calibrated) return { value: baseline, weight: 0, count: 0 };
  const weight = Math.min(calibrated.count, 5) / 5;
  return { value: Math.round(baseline * (1 - weight) + calibrated.rank * weight), weight, count: calibrated.count };
}

function refreshCalibrationStatus() {
  const fb = allFeedback();
  const local = loadLocalFeedback();
  const el = document.getElementById("calibration-status");
  if (!el) return;
  if (fb.length === 0) {
    el.textContent = "No feedback logged yet — predictions are running on the synthetic baseline only.";
  } else {
    el.textContent = `Calibration active: ${fb.length} feedback report(s) in play ` +
      `(${local.length} from this device, ${fb.length - local.length} bundled from prior contributors).`;
  }
}

/* ---------- Rank Predictor ---------- */
document.getElementById("predictor-form").addEventListener("submit", e => {
  e.preventDefault();
  const rank = Number(document.getElementById("p-rank").value);
  const category = document.getElementById("p-category").value;
  const pwd = document.getElementById("p-pwd").value === "yes";
  const quota = document.getElementById("p-quota").value;
  const courseType = document.getElementById("p-coursetype").value;

  const feedbackArr = allFeedback();

  let rows = DATASET.filter(r => {
    if (quota !== "All" && r.quota !== quota) return false;
    if (courseType !== "All" && r.courseType !== courseType) return false;
    return true;
  }).map(r => {
    const baseline = estimateClosingRank(r.urClosingRank, category, pwd);
    const key = [r.quota, r.tier, r.courseType, category, r.round].join("|");
    const calibrated = calibratedRankForBucket(key, feedbackArr);
    const blended = blend(baseline, calibrated);
    return { ...r, predictedClosingRank: blended.value, calibrationCount: blended.count };
  });

  rows = rows.filter(r => rank <= r.predictedClosingRank)
             .sort((a, b) => a.predictedClosingRank - b.predictedClosingRank)
             .slice(0, 25);

  renderPredictorResults(rows, rank);
  refreshCalibrationStatus();
});

function renderPredictorResults(rows, rank) {
  const container = document.getElementById("predictor-results");
  if (rows.length === 0) {
    container.innerHTML = `<div class="empty-state">No matching sample seats found within reach of rank ${rank} for these filters. Try a different category/quota/course-type combination, or remember this is a small illustrative dataset — a "no match" here says nothing about your real chances.</div>`;
    return;
  }
  const rowsHtml = rows.map(r => `
    <tr>
      <td>${r.college}</td>
      <td><span class="pill">${r.tier}</span></td>
      <td>${r.quota}</td>
      <td>${r.course}</td>
      <td>${r.round}</td>
      <td>${r.predictedClosingRank.toLocaleString()}
        ${r.calibrationCount ? `<span class="pill">calibrated ×${r.calibrationCount}</span>` : ""}
      </td>
    </tr>
  `).join("");
  container.innerHTML = `
    <table class="result-table">
      <thead>
        <tr><th>Sample College</th><th>Tier</th><th>Quota</th><th>Course</th><th>Round</th><th>Predicted Closing Rank</th></tr>
      </thead>
      <tbody>${rowsHtml}</tbody>
    </table>
  `;
}

/* ---------- Reservation Calculator ---------- */
document.getElementById("calc-form").addEventListener("submit", e => {
  e.preventDefault();
  const category = document.getElementById("c-category").value;
  const income = Number(document.getElementById("c-income").value) || 0;
  const pwd = document.getElementById("c-pwd").value === "yes";
  const inService = document.getElementById("c-inservice").value === "yes";

  const AIQ_RESERVATION = { "UR": 0, "EWS": 10, "OBC-NCL": 27, "SC": 15, "ST": 7.5 };
  const lines = [];

  lines.push(`Under <strong>AIQ</strong>, ${category === "UR" ? "UR/General candidates compete in the open, unreserved pool." : `${category} candidates are eligible for a reservation of approximately <strong>${AIQ_RESERVATION[category]}%</strong> of AIQ seats.`}`);

  if (pwd) {
    lines.push(`As a <strong>PwD</strong> candidate (≥40% benchmark disability), you're additionally eligible for the horizontal PwD reservation (commonly ~5% of seats), applied within your category.`);
  }

  if (category === "EWS") {
    if (income > 800000) {
      lines.push(`<span class="warn-line">⚠️ Your stated income (₹${income.toLocaleString()}) is above the commonly cited EWS threshold (₹8,00,000/year). Double-check the current official EWS criteria — you may not be eligible this cycle.</span>`);
    } else {
      lines.push(`Your stated income is within the commonly cited EWS threshold (₹8,00,000/year) — but the certificate must also satisfy asset/land-holding conditions and be issued for the current year.`);
    }
  }

  if (inService) {
    lines.push(`In-Service reservation is a <strong>State Quota</strong> category for doctors already employed in that state's government health department — eligibility (years of service, rural posting, etc.) is set independently by each state.`);
  }

  lines.push(`<span class="warn-line">State Quota reservation percentages and rules vary by state and are not modeled here — check your specific state's counseling bulletin.</span>`);

  document.getElementById("calc-results").innerHTML = `
    <div class="calc-summary">
      <h4>Your Reservation Snapshot</h4>
      <ul>${lines.map(l => `<li>${l}</li>`).join("")}</ul>
    </div>
  `;
});

/* ---------- Chatbot ---------- */
function scoreFaq(input, faq) {
  const words = input.toLowerCase().split(/\W+/).filter(Boolean);
  let score = 0;
  faq.keywords.forEach(k => {
    if (input.toLowerCase().includes(k)) score += k.split(" ").length * 2;
  });
  words.forEach(w => {
    if (faq.q.includes(w) && w.length > 2) score += 1;
  });
  return score;
}

function answerQuestion(input) {
  let best = null, bestScore = 0;
  FAQS.forEach(faq => {
    const s = scoreFaq(input, faq);
    if (s > bestScore) { bestScore = s; best = faq; }
  });
  if (best && bestScore > 0) return best.a;
  return "I don't have that in my FAQ list yet. Try rephrasing, check the Guide tab, or ask your official counseling authority. Try one of the suggestions below for what I do know.";
}

function appendChatMsg(text, who) {
  const win = document.getElementById("chat-window");
  const div = document.createElement("div");
  div.className = `chat-msg ${who}`;
  div.textContent = text;
  win.appendChild(div);
  win.scrollTop = win.scrollHeight;
}

document.getElementById("chat-form").addEventListener("submit", e => {
  e.preventDefault();
  const input = document.getElementById("chat-input");
  const text = input.value.trim();
  if (!text) return;
  appendChatMsg(text, "user");
  appendChatMsg(answerQuestion(text), "bot");
  input.value = "";
});

function renderChatSuggestions() {
  const row = document.getElementById("chat-suggestions");
  const sample = FAQS.slice(0, 8);
  row.innerHTML = "";
  sample.forEach(faq => {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "chip";
    chip.textContent = faq.q;
    chip.addEventListener("click", () => {
      appendChatMsg(faq.q, "user");
      appendChatMsg(faq.a, "bot");
    });
    row.appendChild(chip);
  });
}
renderChatSuggestions();

/* ---------- Feedback tab: log, stats, export/import/clear ---------- */
document.getElementById("feedback-form").addEventListener("submit", e => {
  e.preventDefault();
  const entry = {
    rank: Number(document.getElementById("f-rank").value),
    category: document.getElementById("f-category").value,
    pwd: document.getElementById("f-pwd").value === "yes",
    quota: document.getElementById("f-quota").value,
    tier: document.getElementById("f-tier").value,
    courseType: document.getElementById("f-coursetype").value,
    round: document.getElementById("f-round").value,
    outcome: document.getElementById("f-outcome").value,
    source: "local",
    timestamp: Date.now()
  };
  const arr = loadLocalFeedback();
  arr.push(entry);
  saveLocalFeedback(arr);
  e.target.reset();
  refreshFeedbackUI();
  refreshCalibrationStatus();
});

/* Leave-one-out alignment check: for each entry, calibrate from every OTHER
   entry (bundled + local) plus the synthetic baseline for that bucket, then
   see whether that entry's real outcome matches what the calibrated
   prediction would have said. */
function computeAccuracy() {
  const fb = allFeedback();
  if (fb.length === 0) return null;

  let aligned = 0;
  fb.forEach((entry, idx) => {
    const others = fb.filter((_, i) => i !== idx);
    const matchingRows = DATASET.filter(r =>
      r.quota === entry.quota && r.tier === entry.tier && r.courseType === entry.courseType
    );
    if (matchingRows.length === 0) return;
    const baselineAvg = Math.round(
      matchingRows.reduce((sum, r) => sum + estimateClosingRank(r.urClosingRank, entry.category, entry.pwd), 0) / matchingRows.length
    );
    const key = bucketKey(entry);
    const calibrated = calibratedRankForBucket(key, others);
    const predicted = blend(baselineAvg, calibrated).value;

    const isAligned = entry.outcome === "got_seat" ? entry.rank <= predicted : entry.rank > predicted;
    if (isAligned) aligned++;
  });

  return { aligned, total: fb.length, pct: Math.round((aligned / fb.length) * 100) };
}

function refreshFeedbackUI() {
  const local = loadLocalFeedback();
  const fb = allFeedback();

  const statsEl = document.getElementById("feedback-stats");
  const acc = computeAccuracy();
  statsEl.innerHTML = `
    <h3>Self-Reported Accuracy</h3>
    ${acc
      ? `<p>Across ${acc.total} logged report(s) (this device + bundled), predictions aligned with actual outcomes in <strong>${acc.pct}%</strong> of cases (${acc.aligned}/${acc.total}), using leave-one-out calibration.</p>
         <p class="note">Small sample sizes can swing this number a lot — treat it as a rough signal, not a real accuracy guarantee.</p>`
      : `<p class="note">No feedback yet. Log an actual result above to start tracking calibration accuracy.</p>`
    }
  `;

  const logEl = document.getElementById("feedback-log");
  if (local.length === 0) {
    logEl.innerHTML = `<h3>Your Logged Reports</h3><p class="note">Nothing logged on this device yet.</p>`;
  } else {
    const rowsHtml = local.slice().reverse().map((e, revIdx) => {
      const idx = local.length - 1 - revIdx;
      return `
        <tr>
          <td>${new Date(e.timestamp).toLocaleDateString()}</td>
          <td>${e.rank}</td>
          <td>${e.category}${e.pwd ? " (PwD)" : ""}</td>
          <td>${e.quota}</td>
          <td>${e.tier}</td>
          <td>${e.courseType}</td>
          <td>${e.round}</td>
          <td>${e.outcome === "got_seat" ? "Got seat" : "Did not get"}</td>
          <td><button type="button" class="chip" data-del="${idx}">Delete</button></td>
        </tr>
      `;
    }).join("");
    logEl.innerHTML = `
      <h3>Your Logged Reports (${local.length})</h3>
      <table class="result-table">
        <thead><tr><th>Date</th><th>Rank</th><th>Category</th><th>Quota</th><th>Tier</th><th>Course Type</th><th>Round</th><th>Outcome</th><th></th></tr></thead>
        <tbody>${rowsHtml}</tbody>
      </table>
    `;
    logEl.querySelectorAll("[data-del]").forEach(btn => {
      btn.addEventListener("click", () => {
        const arr = loadLocalFeedback();
        arr.splice(Number(btn.dataset.del), 1);
        saveLocalFeedback(arr);
        refreshFeedbackUI();
        refreshCalibrationStatus();
      });
    });
  }
}

document.getElementById("export-feedback").addEventListener("click", () => {
  const arr = loadLocalFeedback();
  const blob = new Blob([JSON.stringify(arr, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `neetpg-feedback-export-${new Date().toISOString().slice(0, 10)}.json`;
  a.click();
  URL.revokeObjectURL(url);
});

document.getElementById("import-feedback").addEventListener("click", () => {
  document.getElementById("import-file-input").click();
});

document.getElementById("import-file-input").addEventListener("change", e => {
  const file = e.target.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = () => {
    try {
      const imported = JSON.parse(reader.result);
      if (!Array.isArray(imported)) throw new Error("not an array");
      const existing = loadLocalFeedback();
      const existingKeys = new Set(existing.map(e => JSON.stringify(e)));
      const merged = existing.slice();
      imported.forEach(e => {
        const k = JSON.stringify(e);
        if (!existingKeys.has(k)) { merged.push(e); existingKeys.add(k); }
      });
      saveLocalFeedback(merged);
      refreshFeedbackUI();
      refreshCalibrationStatus();
    } catch (err) {
      alert("That file doesn't look like a valid feedback export.");
    }
  };
  reader.readAsText(file);
  e.target.value = "";
});

document.getElementById("clear-feedback").addEventListener("click", () => {
  if (confirm("Clear all feedback logged on this device? This can't be undone (export first if you want a backup).")) {
    saveLocalFeedback([]);
    refreshFeedbackUI();
    refreshCalibrationStatus();
  }
});

refreshFeedbackUI();
refreshCalibrationStatus();
