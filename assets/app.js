// app.js — DEBUG VERSION (no fetch, no JSON)

// This version is only to verify that app.js is actually loaded and running.
// It does NOT use events.json. Once you see the debug text in the UI,
// we can go back to the real logic.

document.addEventListener("DOMContentLoaded", function () {
  // Mark that JS ran at all
  console.log("DEBUG: app.js loaded and DOMContentLoaded fired.");

  // Change titles so it's obvious JS is active
  var mainTitleEl = document.querySelector("[data-section-upcoming-title]");
  if (mainTitleEl) {
    mainTitleEl.textContent = "Upcoming (DEBUG MODE)";
  }

  var deadlinesTitleEl = document.querySelector("[data-next-deadlines-title]");
  if (deadlinesTitleEl) {
    deadlinesTitleEl.textContent = "Next deadlines (DEBUG)";
  }

  var congressesTitleEl = document.querySelector("[data-upcoming-congresses-title]");
  if (congressesTitleEl) {
    congressesTitleEl.textContent = "Upcoming congresses (DEBUG)";
  }

  // Put a big debug block in the deadlines column
  var deadlinesContainer = document.querySelector("[data-next-deadlines]");
  if (deadlinesContainer) {
    deadlinesContainer.innerHTML = "";

    var box = document.createElement("div");
    box.style.padding = "24px";
    box.style.borderRadius = "12px";
    box.style.border = "1px solid rgba(255,255,255,0.2)";
    box.style.background = "rgba(255,255,255,0.06)";
    box.style.color = "#fff";
    box.style.fontSize = "16px";
    box.style.lineHeight = "1.4";

    box.textContent =
      "DEBUG: app.js is loaded and running.\n\n" +
      "If you can read this box, the problem is NOT with the HTML shell. " +
      "Then we can safely re-enable the real calendar code using events.json.";

    deadlinesContainer.appendChild(box);
  }

  // Also put a small message in the congresses column so we know both columns are reachable
  var congressesContainer = document.querySelector("[data-upcoming-congresses]");
  if (congressesContainer) {
    congressesContainer.innerHTML = "";

    var msg = document.createElement("div");
    msg.style.padding = "16px";
    msg.style.borderRadius = "12px";
    msg.style.border = "1px dashed rgba(255,255,255,0.25)";
    msg.style.color = "#fff";
    msg.textContent = "DEBUG: congress column reachable.";
    congressesContainer.appendChild(msg);
  }

  // Set the "Last updated" chip to a fixed debug text so we know we can touch it
  var lastUpdatedEl = document.querySelector("[data-last-updated]");
  if (lastUpdatedEl) {
    lastUpdatedEl.textContent = "debug mode";
  }
});