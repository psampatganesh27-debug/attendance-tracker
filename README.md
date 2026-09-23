# 📚 Attendance Tracker

A lightweight, persistent full-stack web application designed for college students to track subject-wise attendance, calculate target percentage thresholds (e.g., 80%), and predict how many classes can be safely skipped or must be attended.

Built with **Python (Flask)** on the backend, **JavaScript/HTML/CSS** on the frontend, and connected to **Turso (libSQL)** via HTTP REST API for multi-device synchronization and permanent cloud storage.

---

## ✨ Key Features

* **Real-time Dashboard:** Displays subject-wise attendance percentage, total classes conducted, attended classes, and status indicators (`SAFE`, `CRITICAL`, `NO_CLASSES`).
* **Boundary & Margin Calculations:** Automatically computes the exact number of future consecutive classes you can safely skip (or must attend) to maintain your target attendance percentage.
* **Daily Attendance Logging:** Quickly mark classes as `PRESENT`, `ABSENT`, or `CANCELLED` for today.
* **Historical Attendance Editor:** Look up and easily modify past attendance records for any subject to fix accidental clicks or account for canceled classes.
* **Automated Semester Log Generation:** Generates class logs for an entire semester date range in a single batch request while automatically filtering out specified holidays and weekends.
* **Persistent Cloud Database:** Uses Turso's HTTP REST API, ensuring zero data loss across server restarts, spin-downs, or re-deployments.
* **Cross-Device Sync:** Seamlessly access and update records from both desktop and mobile browsers.

---

## 🛠️ Tech Stack

* **Backend:** Python 3.x, Flask, Requests
* **Frontend:** HTML5, CSS3, JavaScript (Fetch API)
* **Database:** Turso (libSQL / Distributed SQLite) via HTTP Pipeline API
* **Deployment:** Render Web Service
* **Local Fallback:** Built-in `sqlite3` for offline development

---

## 🚀 How to Deploy Your Own Copy (For Friends & Contributors)

If you want to use this tracker for your own semester, you need your own private database so your records don't mix with anyone else's.

1. **Fork this repository:** Click the "Fork" button at the top right of this GitHub page to copy the code to your own account.
2. **Set Up Turso Database:**
   * Sign up at [turso.tech](https://turso.tech) and create a free database.
   * Retrieve your **Database URL** (`libsql://...`) and an **Auth Token**.
3. **Deploy on Render:**
   * Create a new **Web Service** on [Render](https://render.com) connected to your forked GitHub repository.
   * **Build Command:** `pip install -r requirements.txt`
   * **Start Command:** `gunicorn app:app`
   * Add the following **Environment Variables** in your Render dashboard:
     * `TURSO_DATABASE_URL`: Your Turso database URL
     * `TURSO_AUTH_TOKEN`: Your long Turso authentication token

---

## 📂 Project Structure

```text
├── app.py              # Main Flask application & Turso HTTP API wrapper
├── database.db         # Local SQLite fallback database (git-ignored)
├── requirements.txt    # Python dependencies
├── Procfile            # Render deployment configuration
└── frontend/
    ├── index.html      # Main user interface
    ├── style.css       # Styling & responsive design
    └── script.js       # Dynamic UI rendering & API requests
