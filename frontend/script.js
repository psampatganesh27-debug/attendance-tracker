// --- AUTHENTICATION LOGIC ---
let isRegisterMode = false;

function handleRegisterClick() {
  const targetContainer = document.getElementById('target-pct-container');
  const btn = document.getElementById('btn-register-mode');
  
  if (!isRegisterMode) {
    isRegisterMode = true;
    targetContainer.style.display = 'block';
    btn.textContent = 'Submit Registration';
    showToast("Enter target attendance % and submit", "info");
  } else {
    handleAuth('register');
  }
}

async function checkAuthStatus() {
    try {
        const res = await fetch('/api/auth/me');
        if (res.ok) {
            const data = await res.json();
            document.getElementById('auth-container').style.display = 'none';
            document.getElementById('app-container').style.display = 'block';
            document.getElementById('user-greeting').textContent = `👤 ${data.username}`;
            
            const badge = document.getElementById('nav-target-badge');
            if (badge) {
              const target = data.target_percentage ? parseInt(data.target_percentage) : 80;
              badge.textContent = `🎯 Target: ${target}%`;
            }

            // On mobile, collapse setup by default
            if (window.innerWidth <= 950) {
              const details = document.querySelector('.sidebar-collapsible');
              if (details) details.removeAttribute('open');
            }
            
            fetchDashboard();
            fetchTodayClasses();
            populateSubjectDropdowns();
        } else {
            document.getElementById('auth-container').style.display = 'flex';
            document.getElementById('app-container').style.display = 'none';
        }
    } catch (e) {
        console.error("Auth check failed", e);
        document.getElementById('auth-container').style.display = 'flex';
        document.getElementById('app-container').style.display = 'none';
    }
}

async function handleAuth(action) {
    const username = document.getElementById('auth-username').value.trim();
    const pin = document.getElementById('auth-pin').value.trim();
    const targetInput = document.getElementById('auth-target');
    const target_percentage = targetInput ? parseFloat(targetInput.value) || 80.0 : 80.0;
    
    if (!username || !pin) return showToast("Enter both username and PIN", "error");
    if (!/^\d{4}$/.test(pin)) return showToast("PIN must be exactly 4 digits", "error");

    const payload = { username, pin };
    if (action === 'register') {
      payload.target_percentage = target_percentage;
    }

    try {
        const res = await fetch(`/api/auth/${action}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        
        const data = await res.json();
        if (res.ok) {
            showToast(data.message, "success");
            checkAuthStatus(); 
        } else {
            showToast(data.error || "Authentication failed", "error");
        }
    } catch (err) {
        showToast("Network error during authentication", "error");
    }
}

async function logout() {
    try {
        await fetch('/api/auth/logout', { method: 'POST' });
        document.getElementById('auth-username').value = '';
        document.getElementById('auth-pin').value = '';
        showToast("Logged out successfully", "info");
        checkAuthStatus(); 
    } catch (e) {
        showToast("Failed to logout cleanly", "error");
    }
}

document.addEventListener("DOMContentLoaded", () => {
  checkAuthStatus();

  const extraDateInput = document.getElementById("extra-class-date");
  if (extraDateInput) {
    extraDateInput.value = new Date().toISOString().split("T")[0];
  }

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

  // Handle Delete Account Button
  const btnDeleteAccount = document.getElementById("btn-delete-account");
  if (btnDeleteAccount) {
    btnDeleteAccount.addEventListener("click", async () => {
      const confirmDelete = confirm("CRITICAL WARNING: This will permanently delete your account and ALL your data. This cannot be undone. Proceed?");
      if (!confirmDelete) return;

      const res = await fetch("/api/auth/delete-account", { method: "POST" });
      if (res.ok) {
        showToast("Account deleted forever.", "info");
        checkAuthStatus(); 
      } else {
        showToast("Failed to delete account", "error");
      }
    });
  }
});

function showToast(message, type = "info") {
  const container = document.getElementById("toast-container");
  if (!container) return;

  const toast = document.createElement("div");
  toast.className = `toast ${type}`;
  toast.textContent = message;

  container.appendChild(toast);
  setTimeout(() => { toast.remove(); }, 3000);
}

async function populateSubjectDropdowns() {
  try {
    const res = await fetch("/api/dashboard");
    if (res.status === 401) return checkAuthStatus();
    const subjects = await res.json();
    
    let optionsHTML = '<option value="">-- Choose a Subject --</option>';
    subjects.forEach(sub => {
      optionsHTML += `<option value="${sub.subject_id}">${sub.subject_name}</option>`;
    });

    const schedSelect = document.getElementById("sched-subject-id");
    if (schedSelect) schedSelect.innerHTML = optionsHTML;

    const extraSelect = document.getElementById("extra-subject-id");
    if (extraSelect) extraSelect.innerHTML = optionsHTML;

    const historySelect = document.getElementById("history-subject-id");
    if (historySelect) historySelect.innerHTML = optionsHTML;

    document.querySelectorAll(".subject-dropdown").forEach(select => {
      select.innerHTML = optionsHTML;
    });
  } catch (error) {
    console.error("Error populating dropdowns:", error);
  }
}

async function fetchDashboard() {
  const res = await fetch("/api/dashboard");
  if (res.status === 401) return checkAuthStatus();
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
      <p style="font-size: 0.85rem; color: #a1a1aa; margin-bottom: 8px;"><strong>Total Scheduled:</strong> ${sub.total_semester || 0}</p>
      <div class="message">${sub.message}</div>
    `;
    container.appendChild(card);
  });
}

async function fetchTodayClasses() {
  const res = await fetch("/api/today");
  if (res.status === 401) return checkAuthStatus();
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
                onclick="handleMarkAttendance(${cls.log_id}, 'PRESENT', '${cls.status}', this)">Present</button>
        <button class="btn-absent ${cls.status === 'ABSENT' ? 'active' : ''}" 
                onclick="handleMarkAttendance(${cls.log_id}, 'ABSENT', '${cls.status}', this)">Absent</button>
        <button class="btn-cancel ${cls.status === 'CANCELLED' ? 'active' : ''}" 
                onclick="handleMarkAttendance(${cls.log_id}, 'CANCELLED', '${cls.status}', this)">Cancel</button>
      </div>
    `;
    container.appendChild(card);
  });
}

async function handleMarkAttendance(logId, newStatus, currentStatus, buttonElement) {
  if (currentStatus === newStatus) return;

  const parentDiv = buttonElement.parentElement;
  parentDiv.querySelectorAll('button').forEach(btn => btn.classList.remove('active'));
  buttonElement.classList.add('active');

  parentDiv.querySelectorAll('button').forEach(btn => {
      const btnStatus = btn.textContent.toUpperCase();
      btn.setAttribute('onclick', `handleMarkAttendance(${logId}, '${btnStatus}', '${newStatus}', this)`);
  });

  try {
    const res = await fetch(`/api/attendance/${logId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: newStatus })
    });

    if (res.ok) {
      fetchDashboard(); 
    } else {
      throw new Error("Server rejected update");
    }
  } catch (error) {
    console.error(error);
    showToast("Network error. Reverting status.", "error");
    fetchTodayClasses();
  }
}

async function loadHistory() {
    const subjectId = document.getElementById('history-subject-id').value;
    const container = document.getElementById('history-list');
    
    if (!subjectId) {
        container.innerHTML = '<p class="empty-state">Select a subject to view past classes.</p>';
        return;
    }
    
    container.innerHTML = '<p class="empty-state">Loading past records...</p>';
    
    try {
        const response = await fetch(`/api/history/${subjectId}`);
        const logs = await response.json();
        
        if (logs.length === 0) {
            container.innerHTML = '<p class="empty-state">No past classes found for this subject.</p>';
            return;
        }
        
        let html = '<div style="display: flex; flex-direction: column; gap: 10px;">';
        logs.forEach(log => {
            html += `
                <div class="card" style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 15px; padding: 15px; margin-bottom: 0;">
                    <div><strong>${log.class_date}</strong> &rarr; <strong>${log.status}</strong></div>
                    <div class="status-btns" style="display: flex; gap: 8px; margin-top: 0;">
                        <button class="btn-present ${log.status === 'PRESENT' ? 'active' : ''}" 
                                onclick="updateHistoryStatus(${log.log_id}, 'PRESENT', '${log.status}')">Present</button>
                        <button class="btn-absent ${log.status === 'ABSENT' ? 'active' : ''}" 
                                onclick="updateHistoryStatus(${log.log_id}, 'ABSENT', '${log.status}')">Absent</button>
                        <button class="btn-cancel ${log.status === 'CANCELLED' ? 'active' : ''}" 
                                onclick="updateHistoryStatus(${log.log_id}, 'CANCELLED', '${log.status}')">Cancel</button>
                    </div>
                </div>
            `;
        });
        html += '</div>';
        container.innerHTML = html;
    } catch (error) {
        console.error("Error loading history:", error);
        container.innerHTML = '<p class="empty-state" style="color: var(--danger-color);">Failed to load history.</p>';
    }
}

async function updateHistoryStatus(logId, newStatus, currentStatus) {
    if (currentStatus === newStatus) {
        showToast(`Already marked as ${newStatus}`, "info");
        return;
    }

    try {
        const response = await fetch(`/api/attendance/${logId}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status: newStatus })
        });
        
        if (response.ok) {
            showToast(`Record updated to ${newStatus}`, "success");
            loadHistory(); 
            fetchDashboard(); 
            fetchTodayClasses(); 
        } else {
            showToast("Failed to update status.", "error");
        }
    } catch (error) {
        console.error("Error updating status:", error);
        showToast("Network error while updating.", "error");
    }
}