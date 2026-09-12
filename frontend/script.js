/*

document.addEventListener("DOMContentLoaded", () => {
  fetchDashboard();
  fetchTodayClasses();
  populateSubjectDropdown();

  // Handle Add Subject Form
  document.getElementById("add-subject-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const name = document.getElementById("subject-name").value;
    const res = await fetch("/api/setup/subject", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name })
    });
    if (res.ok) {
      document.getElementById("subject-name").value = "";
      showToast("Subject added successfully!", "success");
      fetchDashboard();
      populateSubjectDropdown();
    } else {
      const err = await res.json();
      showToast(err.error || "Failed to add subject", "error");
    }
  });

  // Handle Add Holiday / Vacation Range Form
  document.getElementById("add-holiday-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const start_date = document.getElementById("holiday-start").value;
    const end_date = document.getElementById("holiday-end").value || start_date;
    const description = document.getElementById("holiday-desc").value;

    const res = await fetch("/api/setup/holiday", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ start_date, end_date, description })
    });
    
    if (res.ok) {
      showToast("Holiday range added successfully", "success");
      document.getElementById("holiday-start").value = "";
      document.getElementById("holiday-end").value = "";
      document.getElementById("holiday-desc").value = "";
    } else {
      const err = await res.json();
      showToast(err.error || "Failed to add holiday", "error");
    }
  });

  // Handle Schedule Mapping Form
  document.getElementById("add-schedule-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const subject_id = parseInt(document.getElementById("sched-subject-id").value);
    const day_of_week = parseInt(document.getElementById("sched-day").value);
    const count = parseInt(document.getElementById("sched-count").value) || 1;

    if (!subject_id) {
      showToast("Please select a valid subject", "error");
      return;
    }

    const scheduleData = [];
    for (let i = 0; i < count; i++) {
      scheduleData.push({ subject_id, day_of_week });
    }

    const res = await fetch("/api/setup/schedule", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(scheduleData)
    });

    if (res.ok) {
      showToast(`Mapped ${count} class(es) for this day successfully!`, "success");
      document.getElementById("sched-count").value = 1;
    } else {
      const err = await res.json();
      showToast(err.error || "Failed to map schedule", "error");
    }
  });

  // Handle Generate Semester Form
  document.getElementById("generate-semester-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const start_date = document.getElementById("start-date").value;
    const end_date = document.getElementById("end-date").value;

    const res = await fetch("/api/generate-semester", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ start_date, end_date })
    });

    const data = await res.json();
    if (res.ok) {
      showToast(data.message, "info");
      fetchTodayClasses();
      fetchDashboard();
    } else {
      showToast(data.error || "Failed to generate semester logs", "error");
    }
  });
});

// Toast Notification Handler
function showToast(message, type = "info") {
  const container = document.getElementById("toast-container");
  if (!container) return;

  const toast = document.createElement("div");
  toast.className = `toast ${type}`;
  toast.textContent = message;

  container.appendChild(toast);

  setTimeout(() => {
    toast.remove();
  }, 3000);
}

// Helper: Populate Subject Dropdown from API
async function populateSubjectDropdown() {
  const res = await fetch("/api/dashboard");
  const subjects = await res.json();
  const select = document.getElementById("sched-subject-id");
  select.innerHTML = '<option value="">Select Subject</option>';

  subjects.forEach(sub => {
    const opt = document.createElement("option");
    opt.value = sub.subject_id;
    opt.textContent = sub.subject_name;
    select.appendChild(opt);
  });
}

// Fetch and render the subject health cards
async function fetchDashboard() {
  const res = await fetch("/api/dashboard");
  const data = await res.json();
  const container = document.getElementById("subject-cards-list");
  container.innerHTML = "";

  if (data.length === 0) {
    container.innerHTML = '<p class="empty-state">No subjects added yet.</p>';
    return;
  }

  data.forEach(sub => {
    const card = document.createElement("div");
    card.className = `card ${sub.status}`;
    card.innerHTML = `
      <h4>${sub.subject_name}</h4>
      <div class="pct">${sub.percentage}%</div>
      <p style="margin-bottom: 4px;"><strong>Conducted:</strong> ${sub.attended} / ${sub.conducted}</p>
      <p style="font-size: 0.85rem; color: #94a3b8; margin-bottom: 8px;"><strong>Total Scheduled in Semester:</strong> ${sub.total_semester || 0}</p>
      <div class="message">${sub.message}</div>
    `;
    container.appendChild(card);
  });
}

// Fetch and render today's class check-ins
async function fetchTodayClasses() {
  const res = await fetch("/api/today");
  const data = await res.json();
  const container = document.getElementById("today-classes-list");
  container.innerHTML = "";

  if (data.length === 0) {
    container.innerHTML = '<p class="empty-state">No classes scheduled for today.</p>';
    return;
  }

  const subjectCounts = {};

  data.forEach((cls) => {
    subjectCounts[cls.subject_name] = (subjectCounts[cls.subject_name] || 0) + 1;
    const classNumber = subjectCounts[cls.subject_name];

    const card = document.createElement("div");
    card.className = "card";
    card.innerHTML = `
      <h4>${cls.subject_name} ${classNumber > 1 ? `(Session ${classNumber})` : ""}</h4>
      <p>Status: <strong>${cls.status}</strong></p>
      <div class="status-btns">
        <button class="btn-present ${cls.status === 'PRESENT' ? 'active' : ''}" 
                onclick="handleMarkAttendance(${cls.log_id}, 'PRESENT', '${cls.status}')">Present</button>
        <button class="btn-absent ${cls.status === 'ABSENT' ? 'active' : ''}" 
                onclick="handleMarkAttendance(${cls.log_id}, 'ABSENT', '${cls.status}')">Absent</button>
        <button class="btn-cancel ${cls.status === 'CANCELLED' ? 'active' : ''}" 
                onclick="handleMarkAttendance(${cls.log_id}, 'CANCELLED', '${cls.status}')">Cancel</button>
      </div>
    `;
    container.appendChild(card);
  });
}

// Wrapper to prevent accidental status overrides
async function handleMarkAttendance(logId, newStatus, currentStatus) {
  if (currentStatus === newStatus) {
    showToast(`Already marked as ${newStatus}`, "info");
    return;
  }

  if (currentStatus !== 'PENDING') {
    showToast(`Updated from ${currentStatus} to ${newStatus}`, "info");
  }

  await markAttendance(logId, newStatus);
}

// Update class attendance status
async function markAttendance(logId, status) {
  const res = await fetch(`/api/attendance/${logId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status })
  });
  if (res.ok) {
    showToast(`Marked as ${status}`, "success");
    fetchTodayClasses();
    fetchDashboard();
  } else {
    showToast("Failed to update status", "error");
  }
}

*/

//WITH EXTRA CLASSES

document.addEventListener("DOMContentLoaded", () => {
  // Set default date for Extra Class to Today
  const extraDateInput = document.getElementById("extra-class-date");
  if (extraDateInput) {
    extraDateInput.value = new Date().toISOString().split("T")[0];
  }

  fetchDashboard();
  fetchTodayClasses();
  populateSubjectDropdowns();

  // Handle Add Subject Form
  document.getElementById("add-subject-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const name = document.getElementById("subject-name").value;
    const res = await fetch("/api/setup/subject", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name })
    });
    if (res.ok) {
      document.getElementById("subject-name").value = "";
      showToast("Subject added successfully!", "success");
      fetchDashboard();
      populateSubjectDropdowns();
    } else {
      const err = await res.json();
      showToast(err.error || "Failed to add subject", "error");
    }
  });

  // Handle Add Holiday Range Form
  document.getElementById("add-holiday-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const start_date = document.getElementById("holiday-start").value;
    const end_date = document.getElementById("holiday-end").value || start_date;
    const description = document.getElementById("holiday-desc").value;

    const res = await fetch("/api/setup/holiday", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ start_date, end_date, description })
    });
    
    if (res.ok) {
      showToast("Holiday range added successfully", "success");
      document.getElementById("holiday-start").value = "";
      document.getElementById("holiday-end").value = "";
      document.getElementById("holiday-desc").value = "";
    } else {
      const err = await res.json();
      showToast(err.error || "Failed to add holiday", "error");
    }
  });

  // Handle Schedule Mapping Form
  document.getElementById("add-schedule-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const subject_id = parseInt(document.getElementById("sched-subject-id").value);
    const day_of_week = parseInt(document.getElementById("sched-day").value);
    const count = parseInt(document.getElementById("sched-count").value) || 1;

    if (!subject_id) {
      showToast("Please select a valid subject", "error");
      return;
    }

    const scheduleData = [];
    for (let i = 0; i < count; i++) {
      scheduleData.push({ subject_id, day_of_week });
    }

    const res = await fetch("/api/setup/schedule", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(scheduleData)
    });

    if (res.ok) {
      showToast(`Mapped ${count} class(es) for this day successfully!`, "success");
      document.getElementById("sched-count").value = 1;
    } else {
      const err = await res.json();
      showToast(err.error || "Failed to map schedule", "error");
    }
  });

  // Handle Generate Semester Form
  document.getElementById("generate-semester-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const start_date = document.getElementById("start-date").value;
    const end_date = document.getElementById("end-date").value;

    const res = await fetch("/api/generate-semester", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ start_date, end_date })
    });

    const data = await res.json();
    if (res.ok) {
      showToast(data.message, "info");
      fetchTodayClasses();
      fetchDashboard();
    } else {
      showToast(data.error || "Failed to generate semester logs", "error");
    }
  });

  // Handle Add Extra Class Form
  document.getElementById("add-extra-class-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const subject_id = parseInt(document.getElementById("extra-subject-id").value);
    const class_date = document.getElementById("extra-class-date").value;
    const status = document.getElementById("extra-class-status").value;

    if (!subject_id) {
      showToast("Select a subject for the extra class", "error");
      return;
    }

    const res = await fetch("/api/attendance/extra", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ subject_id, class_date, status })
    });

    if (res.ok) {
      showToast("Extra class added!", "success");
      fetchTodayClasses();
      fetchDashboard();
    } else {
      const err = await res.json();
      showToast(err.error || "Failed to add extra class", "error");
    }
  });

  // Handle Reset Database Button
  document.getElementById("btn-reset-db").addEventListener("click", async () => {
    const confirmReset = confirm("Are you sure? This will permanently wipe all subjects, schedules, and attendance logs!");
    if (!confirmReset) return;

    const res = await fetch("/api/setup/reset-database", { method: "POST" });
    if (res.ok) {
      showToast("Database completely reset", "info");
      fetchTodayClasses();
      fetchDashboard();
      populateSubjectDropdowns();
    } else {
      showToast("Failed to reset database", "error");
    }
  });
});

// Toast Notification Handler
function showToast(message, type = "info") {
  const container = document.getElementById("toast-container");
  if (!container) return;

  const toast = document.createElement("div");
  toast.className = `toast ${type}`;
  toast.textContent = message;

  container.appendChild(toast);

  setTimeout(() => {
    toast.remove();
  }, 3000);
}

// Helper: Populate all Subject Dropdowns
async function populateSubjectDropdowns() {
  const res = await fetch("/api/dashboard");
  const subjects = await res.json();
  const dropdowns = document.querySelectorAll(".subject-dropdown");
  // Add this inside populateSubjectDropdowns() where the other dropdowns are filled
  const historySelect = document.getElementById('history-subject-id');
  if (historySelect) historySelect.innerHTML = '<option value="">-- Choose Subject --</option>' + options;

  dropdowns.forEach((select) => {
    select.innerHTML = '<option value="">Select Subject</option>';
    subjects.forEach((sub) => {
      const opt = document.createElement("option");
      opt.value = sub.subject_id;
      opt.textContent = sub.subject_name;
      select.appendChild(opt);
    });
  });
}

// Fetch and render subject health cards
async function fetchDashboard() {
  const res = await fetch("/api/dashboard");
  const data = await res.json();
  const container = document.getElementById("subject-cards-list");
  container.innerHTML = "";

  if (data.length === 0) {
    container.innerHTML = '<p class="empty-state">No subjects added yet.</p>';
    return;
  }

  data.forEach((sub) => {
    const card = document.createElement("div");
    card.className = `card ${sub.status}`;
    card.innerHTML = `
      <h4>${sub.subject_name}</h4>
      <div class="pct">${sub.percentage}%</div>
      <p style="margin-bottom: 4px;"><strong>Conducted:</strong> ${sub.attended} / ${sub.conducted}</p>
      <p style="font-size: 0.85rem; color: #94a3b8; margin-bottom: 8px;"><strong>Total Scheduled in Semester:</strong> ${sub.total_semester || 0}</p>
      <div class="message">${sub.message}</div>
    `;
    container.appendChild(card);
  });
}

// Fetch and render today's class check-ins
async function fetchTodayClasses() {
  const res = await fetch("/api/today");
  const data = await res.json();
  const container = document.getElementById("today-classes-list");
  container.innerHTML = "";

  if (data.length === 0) {
    container.innerHTML = '<p class="empty-state">No classes scheduled for today.</p>';
    return;
  }

  const subjectCounts = {};

  data.forEach((cls) => {
    subjectCounts[cls.subject_name] = (subjectCounts[cls.subject_name] || 0) + 1;
    const classNumber = subjectCounts[cls.subject_name];

    const card = document.createElement("div");
    card.className = "card";
    card.innerHTML = `
      <h4>${cls.subject_name} ${classNumber > 1 ? `(Session ${classNumber})` : ""}</h4>
      <p>Status: <strong>${cls.status}</strong></p>
      <div class="status-btns">
        <button class="btn-present ${cls.status === 'PRESENT' ? 'active' : ''}" 
                onclick="handleMarkAttendance(${cls.log_id}, 'PRESENT', '${cls.status}')">Present</button>
        <button class="btn-absent ${cls.status === 'ABSENT' ? 'active' : ''}" 
                onclick="handleMarkAttendance(${cls.log_id}, 'ABSENT', '${cls.status}')">Absent</button>
        <button class="btn-cancel ${cls.status === 'CANCELLED' ? 'active' : ''}" 
                onclick="handleMarkAttendance(${cls.log_id}, 'CANCELLED', '${cls.status}')">Cancel</button>
      </div>
    `;
    container.appendChild(card);
  });
}

// Handler for attendance updates
async function handleMarkAttendance(logId, newStatus, currentStatus) {
  if (currentStatus === newStatus) {
    showToast(`Already marked as ${newStatus}`, "info");
    return;
  }

  if (currentStatus !== 'PENDING') {
    showToast(`Updated from ${currentStatus} to ${newStatus}`, "info");
  }

  await markAttendance(logId, newStatus);
}

// Update class attendance status
async function markAttendance(logId, status) {
  const res = await fetch(`/api/attendance/${logId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status })
  });
  if (res.ok) {
    showToast(`Marked as ${status}`, "success");
    fetchTodayClasses();
    fetchDashboard();
  } else {
    showToast("Failed to update status", "error");
  }
}

// Check class attendance history
async function loadHistory() {
    const subjectId = document.getElementById('history-subject-id').value;
    const container = document.getElementById('history-list');
    
    if (!subjectId) {
        container.innerHTML = '<p style="color: gray; font-size: 0.9em;">Select a subject to view past records.</p>';
        return;
    }
    
    container.innerHTML = 'Loading past records...';
    
    try {
        const response = await fetch(`/api/history/${subjectId}`);
        const logs = await response.json();
        
        if (logs.length === 0) {
            container.innerHTML = '<p>No past classes found for this subject.</p>';
            return;
        }
        
        let html = '<div style="display: flex; flex-direction: column; gap: 10px;">';
        logs.forEach(log => {
            html += `
                <div style="border: 1px solid #ccc; padding: 10px; border-radius: 5px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px;">
                    <div><strong>${log.class_date}</strong>: Current Status - <em>${log.status}</em></div>
                    <div style="display: flex; gap: 5px;">
                        <button onclick="updateHistoryStatus(${log.log_id}, 'PRESENT')" style="padding: 5px 10px; cursor: pointer;">Present</button>
                        <button onclick="updateHistoryStatus(${log.log_id}, 'ABSENT')" style="padding: 5px 10px; cursor: pointer;">Absent</button>
                        <button onclick="updateHistoryStatus(${log.log_id}, 'CANCELLED')" style="padding: 5px 10px; cursor: pointer;">Cancelled</button>
                    </div>
                </div>
            `;
        });
        html += '</div>';
        container.innerHTML = html;
    } catch (error) {
        console.error("Error loading history:", error);
        container.innerHTML = '<p style="color: red;">Failed to load history.</p>';
    }
}

async function updateHistoryStatus(logId, newStatus) {
    try {
        const response = await fetch(`/api/attendance/${logId}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status: newStatus })
        });
        
        if (response.ok) {
            // If you have a showToast function, use it here
            alert(`Record updated to ${newStatus}`);
            loadHistory(); // Instantly refresh the list to show the new status
            fetchDashboard(); // Refresh the main dashboard percentages
        } else {
            alert("Failed to update status.");
        }
    } catch (error) {
        console.error("Error updating status:", error);
    }
}