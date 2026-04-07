/**
 * app.js — ShiftSync frontend logic
 *
 * State machine: login → upload → preview → results
 * Each step is a <section> that gets shown/hidden.
 */

// ----------------------------------------------------------------
// State
// ----------------------------------------------------------------
let allShifts = [];
let filteredShifts = [];

// ----------------------------------------------------------------
// DOM references
// ----------------------------------------------------------------
const authPill    = document.getElementById("auth-status");
const authLabel   = document.getElementById("auth-label");

const stepLogin   = document.getElementById("step-login");
const stepUpload  = document.getElementById("step-upload");
const stepPreview = document.getElementById("step-preview");
const stepResults = document.getElementById("step-results");

const dropZone    = document.getElementById("drop-zone");
const csvInput    = document.getElementById("csv-input");
const feedback    = document.getElementById("upload-feedback");

const previewSummary = document.getElementById("preview-summary");
const previewBody    = document.getElementById("preview-body");
const parseErrors    = document.getElementById("parse-errors");
const btnReupload    = document.getElementById("btn-reupload");
const btnSync        = document.getElementById("btn-sync");
const btnIcs         = document.getElementById("btn-ics");

const btnLogout   = document.getElementById("btn-logout");
const statCreated = document.getElementById("stat-created");
const statSkipped = document.getElementById("stat-skipped");
const statFailed  = document.getElementById("stat-failed");
const resultDetails = document.getElementById("result-details");
const btnReset    = document.getElementById("btn-reset");


// ----------------------------------------------------------------
// Step management
// ----------------------------------------------------------------
function showOnly(section) {
  [stepLogin, stepUpload, stepPreview, stepResults].forEach(s => {
    s.classList.toggle("hidden", s !== section);
  });
}

// ----------------------------------------------------------------
// Auth check — runs on page load
// ----------------------------------------------------------------
async function checkAuth() {
  try {
    const res  = await fetch("/auth/status");
    const data = await res.json();

    if (data.authenticated) {
      authPill.classList.add("logged-in");
      authPill.classList.remove("logged-out");
      authLabel.textContent = "Connected";
      btnLogout.style.display = "inline-flex";
      showOnly(stepUpload);
    } else {
      authPill.classList.add("logged-out");
      authPill.classList.remove("logged-in");
      authLabel.textContent = "Not connected";
      btnLogout.style.display = "none";
      showOnly(stepLogin);
    }
  } catch {
    authLabel.textContent = "Error";
    showOnly(stepLogin);
  }
}


// ----------------------------------------------------------------
// File upload helpers
// ----------------------------------------------------------------
function showFeedback(message, type = "info") {
  feedback.textContent = message;
  feedback.className = `feedback ${type}`;
}

function hideFeedback() {
  feedback.className = "feedback hidden";
}

async function handleFile(file) {
  if (!file) return;
  if (!file.name.match(/\.(csv|xlsx)$/i)) {
    showFeedback("Only .csv and .xlsx files are accepted.", "error");
    return;
  }

  showFeedback(`Parsing ${file.name}…`);

  const formData = new FormData();
  formData.append("file", file);

  try {
    const res  = await fetch("/upload", { method: "POST", body: formData });
    const data = await res.json();

    if (!res.ok) {
      showFeedback(data.error || "Upload failed.", "error");
      return;
    }

    hideFeedback();
    renderPreview(data);

  } catch (err) {
    showFeedback("Network error. Please try again.", "error");
  }
}

function renderPreview(data) {
  allShifts = [...data.shifts].sort((a, b) => a.date.localeCompare(b.date));

  // Parse errors
  if (data.errors && data.errors.length > 0) {
    parseErrors.innerHTML = data.errors
      .map(e => `Row ${e.row}: ${esc(e.message)}`)
      .join("<br>");
    parseErrors.classList.remove("hidden");
  } else {
    parseErrors.classList.add("hidden");
  }

  // Reset filter and render
  const filterInput = document.getElementById("employee-filter");
  if (filterInput) filterInput.value = "";
  applyFilter();

  showOnly(stepPreview);
}

function applyFilter() {
  const filterInput = document.getElementById("employee-filter");
  const query = filterInput ? filterInput.value.trim().toLowerCase() : "";
  filteredShifts = query
    ? allShifts.filter(s => s.employee.toLowerCase().includes(query))
    : allShifts;

  const errorNote = "";
  previewSummary.textContent =
    `Showing ${filteredShifts.length} of ${allShifts.length} shift${allShifts.length !== 1 ? "s" : ""}.`;

  previewBody.innerHTML = "";
  for (const s of filteredShifts) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${esc(s.employee)}</td>
      <td>${esc(formatDate(s.date))}</td>
      <td>${esc(to12hr(s.start_time))}</td>
      <td>${esc(to12hr(s.end_time))}</td>
    `;
    previewBody.appendChild(tr);
  }
}


// ----------------------------------------------------------------
// Sync
// ----------------------------------------------------------------
async function syncShifts() {
  if (!filteredShifts.length) {
    alert("No shifts to sync.");
    return;
  }

  const filterInput = document.getElementById("employee-filter");
  const filterValue = filterInput ? filterInput.value.trim() : "";
  if (!filterValue) {
    const confirmed = confirm(
      `⚠️ No name filter is set — this will sync ALL ${filteredShifts.length} shifts to your calendar.\n\nAre you sure?`
    );
    if (!confirmed) return;
  }

  btnSync.classList.add("loading");
  btnSync.textContent = "Syncing…";

  try {
    const res = await fetch("/sync", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(filteredShifts),
    });
    const data = await res.json();

    if (!res.ok) {
      alert(data.error || "Sync failed.");
      btnSync.classList.remove("loading");
      btnSync.textContent = "Sync to Calendar →";
      return;
    }

    renderResults(data);

  } catch (err) {
    alert("Network error during sync: " + err.message);
    btnSync.classList.remove("loading");
    btnSync.textContent = "Sync to Calendar →";
  }
}

function renderResults(data) {
  statCreated.textContent = data.created;
  statSkipped.textContent = data.skipped;
  statFailed.textContent  = data.failed;

  resultDetails.innerHTML = data.results
    .map(r => {
      const cls = `r-${r.status}`;
      const icon = r.status === "created" ? "✓" : r.status === "skipped" ? "–" : "✗";
      return `<span class="${cls}">${icon} ${esc(r.shift)}</span>`;
    })
    .join("<br>");

  btnSync.classList.remove("loading");
  btnSync.textContent = "Sync to Calendar →";
  showOnly(stepResults);
}


// ----------------------------------------------------------------
// Drag-and-drop
// ----------------------------------------------------------------
dropZone.addEventListener("dragover", e => {
  e.preventDefault();
  dropZone.classList.add("drag-over");
});

dropZone.addEventListener("dragleave", () => {
  dropZone.classList.remove("drag-over");
});

dropZone.addEventListener("drop", e => {
  e.preventDefault();
  dropZone.classList.remove("drag-over");
  const file = e.dataTransfer.files[0];
  handleFile(file);
});

dropZone.addEventListener("click", () => csvInput.click());

csvInput.addEventListener("change", () => {
  handleFile(csvInput.files[0]);
  csvInput.value = ""; // reset so same file can be re-selected
});


// ----------------------------------------------------------------
// Filter wiring (input is injected into the DOM on preview step)
// ----------------------------------------------------------------
document.addEventListener("input", e => {
  if (e.target.id === "employee-filter") applyFilter();
});

// ----------------------------------------------------------------
// Button wiring
// ----------------------------------------------------------------
btnReupload.addEventListener("click", () => {
  hideFeedback();
  showOnly(stepUpload);
});

btnSync.addEventListener("click", syncShifts);

btnIcs.addEventListener("click", async () => {
  if (!filteredShifts.length) { alert("No shifts to download."); return; }

  const filterInput = document.getElementById("employee-filter");
  const filterValue = filterInput ? filterInput.value.trim() : "";
  if (!filterValue) {
    const confirmed = confirm(
      `⚠️ No name filter is set — this will download ALL ${filteredShifts.length} shifts.\n\nAre you sure?`
    );
    if (!confirmed) return;
  }

  const res = await fetch("/download-ics", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(filteredShifts),
  });
  if (!res.ok) { alert("Failed to generate .ics file."); return; }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "shifts.ics";
  a.click();
  URL.revokeObjectURL(url);
});

btnReset.addEventListener("click", () => {
  hideFeedback();
  previewBody.innerHTML = "";
  showOnly(stepUpload);
});


// ----------------------------------------------------------------
// Utility
// ----------------------------------------------------------------
function esc(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function to12hr(timeStr) {
  const [h, m] = timeStr.split(":").map(Number);
  const period = h >= 12 ? "PM" : "AM";
  const hour = h % 12 || 12;
  return `${hour}:${String(m).padStart(2, "0")} ${period}`;
}

function formatDate(dateStr) {
  const [y, mo, d] = dateStr.split("-");
  const months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
  return `${months[parseInt(mo, 10) - 1]} ${parseInt(d, 10)}, ${y}`;
}


// ----------------------------------------------------------------
// Boot
// ----------------------------------------------------------------
checkAuth();
