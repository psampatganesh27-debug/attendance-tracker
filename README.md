# 🎓 CampusTrack

CampusTrack is a production-grade, mobile-first web application designed to help students effortlessly manage their academic attendance, map out their weekly schedules, and calculate class buffers based on personalized targets.

Built with a focus on speed, privacy, and UX, it features an intuitive dashboard, dynamic mathematical forecasting, and seamless local or cloud-based data storage.
🔗 Live Demo: https://attendance-tracker-ssgx.onrender.com

Built with ❤️ for students who want to take control of their time.
---

## ✨ Key Features

**🔐 Frictionless Authentication**

4-Digit PIN System: Fast, mobile-friendly login using masked numeric PINs (immune to aggressive browser credential warnings).
Persistent Sessions: Secure, long-term cookies keep you logged in across device restarts.
Custom Targets: Users define their own attendance threshold requirement (e.g., 75%, 80%, 85%) during registration.


**📊 Dynamic Dashboard & Math Engine**

Today's Schedule: Instantly view and mark attendance (Present, Absent, Cancel) for the current day's mapped classes.
Smart Forecasting: Automatically calculates if you are in the "Safe" or "Critical" zone. Tells you exactly how many classes you can afford to skip, or how many you must attend to maintain your target %.
History Editor: Easily fix past mistakes by editing the status of previously held classes.


**⚙️ Semester Setup Engine**
Weekly Timetable: Map out your entire week subject-by-subject.
Holiday Blackouts: Define vacation dates or exam weeks so the system knows when not to schedule classes.
Auto-Generator: Generates a full semester of PENDING class logs in seconds, automatically skipping weekends and your custom blackout dates.


**🎨 Premium UI/UX Polish**

Mobile-First Design: Collapsible accordion setup sheets and compact dual-column grid layouts for seamless smartphone usage.
Skeleton Loaders: Prevents text-flicker and provides smooth, pulsing visual feedback while data fetches.
Status Glows: Color-coded gradient edges (Emerald for Safe, Rose for Critical) for quick visual scanning.
Haptic Feedback: Native :active press states on buttons for tactile, satisfying interactions.


**⚠️ Danger Zone Features**

Built-in tools to give users complete control over their data footprint:
Start Fresh: Wipes all personal subjects, schedules, and logs while keeping the user account active.
Delete Account: Completely and permanently purges the user profile and all relational database rows from the server.

---

## 🛠️ Tech Stack

* **Backend:** Python, Flask, Flask-Login, Werkzeug (Security/Hashing)
* **Frontend:** Vanilla HTML5, CSS3 (CSS Variables, Flexbox/Grid), Vanilla JavaScript (ES6+ Fetch API)
* **Database:** SQLite3 (Local) / Turso (Production Cloud via HTTP API)
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
CampusTrack/
│
├── app.py                 # Core Flask backend, routing, API, and math logic
├── database.db            # Auto-generated SQLite database (local mode)
├── frontend/
│   ├── index.html         # Single-page application UI structure
│   ├── style.css          # Theming, responsive layouts, and animations
│   └── script.js          # DOM manipulation, API fetching, and state management
└── README.md              # Project documentation
---

