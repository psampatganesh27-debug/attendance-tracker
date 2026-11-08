from flask import Flask, request, jsonify, render_template, session
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import requests
import os
from datetime import datetime, timedelta, timezone

def get_ist_now():
    ist_offset = timedelta(hours=5, minutes=30)
    return datetime.now(timezone.utc) + ist_offset

app = Flask(__name__, static_folder='frontend', template_folder='frontend')
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "fallback-secret-key-change-in-production")

TURSO_DATABASE_URL = os.environ.get("TURSO_DATABASE_URL")
TURSO_AUTH_TOKEN = os.environ.get("TURSO_AUTH_TOKEN")

# --- LOGIN MANAGER SETUP ---
login_manager = LoginManager()
login_manager.init_app(app)

class User(UserMixin):
    def __init__(self, id, username):
        self.id = id
        self.username = username

@login_manager.user_loader
def load_user(user_id):
    db = get_db()
    user = db.fetchone("SELECT * FROM users WHERE id = ?", (int(user_id),))
    db.close()
    if user:
        return User(user['id'], user['username'])
    return None

@login_manager.unauthorized_handler
def unauthorized():
    return jsonify({"error": "Unauthorized"}), 401

# --- DATABASE WRAPPERS (Unchanged functionality) ---
class TursoHTTPDatabase:
    def __init__(self, url, token):
        clean_url = url.strip().replace("libsql://", "https://")
        if not clean_url.endswith("/v2/pipeline"):
            clean_url = clean_url.rstrip("/") + "/v2/pipeline"
        self.url = clean_url
        self.headers = {"Authorization": f"Bearer {token.strip()}", "Content-Type": "application/json"}

    def _format_args(self, args):
        formatted_args = []
        for arg in args:
            if arg is None: formatted_args.append({"type": "null"})
            elif isinstance(arg, int): formatted_args.append({"type": "integer", "value": str(arg)})
            elif isinstance(arg, float): formatted_args.append({"type": "float", "value": arg})
            else: formatted_args.append({"type": "text", "value": str(arg)})
        return formatted_args

    def execute_pipeline(self, statements):
        requests_payload = [{"type": "execute", "stmt": {"sql": sql, "args": self._format_args(args or [])}} for sql, args in statements]
        requests_payload.append({"type": "close"})
        res = requests.post(self.url, json={"requests": requests_payload}, headers=self.headers, timeout=30)
        return res.json()

    def execute_raw(self, sql, args=None):
        data = self.execute_pipeline([(sql, args or [])])
        results = data["results"][0]
        if results["type"] == "error": raise Exception(f"Turso Error: {results['error']['message']}")
        return results.get("response", {}).get("result", {})

    def fetchall(self, sql, args=None):
        res = self.execute_raw(sql, args)
        cols = [c["name"] for c in res.get("cols", [])]
        rows = []
        for r in res.get("rows", []):
            row_dict = {}
            for idx, col_name in enumerate(cols):
                val = r[idx]["value"] if r[idx]["type"] != "null" else None
                if r[idx]["type"] == "integer" and val is not None: val = int(val)
                elif r[idx]["type"] == "float" and val is not None: val = float(val)
                row_dict[col_name] = val
            rows.append(row_dict)
        return rows

    def fetchone(self, sql, args=None):
        rows = self.fetchall(sql, args)
        return rows[0] if rows else None

    def execute(self, sql, args=None):
        self.execute_raw(sql, args)

class DBConnection:
    def __init__(self):
        if TURSO_DATABASE_URL and TURSO_AUTH_TOKEN:
            self.mode = "TURSO"
            self.turso = TursoHTTPDatabase(TURSO_DATABASE_URL, TURSO_AUTH_TOKEN)
        else:
            self.mode = "SQLITE"
            self.conn = sqlite3.connect("database.db", timeout=10)
            self.conn.row_factory = sqlite3.Row

    def fetchall(self, sql, args=None):
        if self.mode == "TURSO": return self.turso.fetchall(sql, args)
        cur = self.conn.cursor()
        return [dict(r) for r in cur.execute(sql, args or ()).fetchall()]

    def fetchone(self, sql, args=None):
        if self.mode == "TURSO": return self.turso.fetchone(sql, args)
        row = self.conn.cursor().execute(sql, args or ()).fetchone()
        return dict(row) if row else None

    def execute(self, sql, args=None):
        if self.mode == "TURSO": self.turso.execute(sql, args)
        else:
            self.conn.cursor().execute(sql, args or ())
            self.conn.commit()

    def execute_batch(self, statements):
        if self.mode == "TURSO": self.turso.execute_pipeline(statements)
        else:
            cur = self.conn.cursor()
            for sql, args in statements: cur.execute(sql, args)
            self.conn.commit()

    def close(self):
        if self.mode == "SQLITE": self.conn.close()

def get_db():
    db = DBConnection()
    try:
        # Check if new multi-tenant tables exist
        tbl = db.fetchone("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        if not tbl:
            # Force wipe old single-tenant tables to prevent schema clashes
            db.execute("DROP TABLE IF EXISTS attendance_logs")
            db.execute("DROP TABLE IF EXISTS holidays")
            db.execute("DROP TABLE IF EXISTS schedule")
            db.execute("DROP TABLE IF EXISTS subjects")
            
            db.execute("CREATE TABLE users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE, password_hash TEXT)")
            db.execute("CREATE TABLE subjects (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, name TEXT, target_percentage REAL, UNIQUE(user_id, name))")
            db.execute("CREATE TABLE schedule (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, subject_id INTEGER, day_of_week INTEGER)")
            db.execute("CREATE TABLE holidays (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, holiday_date TEXT, description TEXT, UNIQUE(user_id, holiday_date))")
            db.execute("CREATE TABLE attendance_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, subject_id INTEGER, class_date TEXT, status TEXT)")
    except Exception as e:
        print(f"Table init error: {e}")
    return db

# --- MATH LOGIC ---
def calculate_stats(attended, conducted, total_semester, target_pct=0.80):
    if conducted == 0: return {"percentage": 100.0, "status": "NO_CLASSES", "message": "No classes held yet"}
    current_pct = attended / conducted
    if current_pct >= target_pct:
        skippable = int((attended - (target_pct * conducted)) / target_pct)
        return {"percentage": round(current_pct * 100, 1), "status": "SAFE", "message": f"Safe to skip next {skippable} class(es)" if skippable > 0 else "On track (80% boundary)"}
    required = int(-(-((target_pct * conducted) - attended) // (1 - target_pct)))
    remaining = max(0, total_semester - conducted)
    if total_semester > 0 and required > remaining:
        return {"percentage": round(current_pct * 100, 1), "status": "CRITICAL", "message": f"Cannot reach {int(target_pct*100)}%! Max possible: {round(((attended + remaining) / total_semester) * 100, 1)}%"}
    return {"percentage": round(current_pct * 100, 1), "status": "CRITICAL", "message": f"Must attend next {required} class(es)"}


@app.route('/')
def index():
    return render_template('index.html')

# --- AUTH ROUTES ---
@app.route('/api/auth/register', methods=['POST'])
def register():
    data = request.json
    username, pin = data.get('username'), data.get('pin')
    
    if not username or not pin: 
        return jsonify({"error": "Missing fields"}), 400
    if not pin.isdigit() or len(pin) < 4: 
        return jsonify({"error": "PIN must be at least 4 digits"}), 400
    
    db = get_db()
    try:
        # We still store it in the password_hash column to avoid database schema migrations
        db.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", (username, generate_password_hash(pin)))
        user = db.fetchone("SELECT * FROM users WHERE username = ?", (username,))
        login_user(User(user['id'], user['username']))
        return jsonify({"message": "Registered successfully"})
    except Exception:
        return jsonify({"error": "Username already exists"}), 400
    finally:
        db.close()

@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.json
    db = get_db()
    user = db.fetchone("SELECT * FROM users WHERE username = ?", (data.get('username'),))
    db.close()
    
    if user and check_password_hash(user['password_hash'], data.get('pin')):
        login_user(User(user['id'], user['username']))
        return jsonify({"message": "Logged in successfully"})
    return jsonify({"error": "Invalid credentials"}), 401

@app.route('/api/auth/delete-account', methods=['POST'])
@login_required
def delete_account():
    db = get_db()
    try:
        # Purge all data owned by the user
        db.execute("DELETE FROM attendance_logs WHERE user_id = ?", (current_user.id,))
        db.execute("DELETE FROM holidays WHERE user_id = ?", (current_user.id,))
        db.execute("DELETE FROM schedule WHERE user_id = ?", (current_user.id,))
        db.execute("DELETE FROM subjects WHERE user_id = ?", (current_user.id,))
        # Delete the user account itself
        db.execute("DELETE FROM users WHERE id = ?", (current_user.id,))
        
        logout_user()
        return jsonify({"message": "Account and all data permanently deleted."}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()

@app.route('/api/auth/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    return jsonify({"message": "Logged out"})

@app.route('/api/auth/me', methods=['GET'])
def get_me():
    if current_user.is_authenticated:
        return jsonify({"username": current_user.username})
    return jsonify({"error": "Not logged in"}), 401


# --- PROTECTED APP ROUTES ---
@app.route('/api/dashboard', methods=['GET'])
@login_required
def get_dashboard():
    db = get_db()
    subjects = db.fetchall("SELECT * FROM subjects WHERE user_id = ?", (current_user.id,))
    summary = []
    for sub in subjects:
        total_semester = db.fetchone("SELECT COUNT(*) as c FROM attendance_logs WHERE subject_id = ? AND user_id = ? AND status != 'CANCELLED'", (sub['id'], current_user.id))['c']
        conducted = db.fetchone("SELECT COUNT(*) as c FROM attendance_logs WHERE subject_id = ? AND user_id = ? AND status IN ('PRESENT', 'ABSENT')", (sub['id'], current_user.id))['c']
        attended = db.fetchone("SELECT COUNT(*) as c FROM attendance_logs WHERE subject_id = ? AND user_id = ? AND status = 'PRESENT'", (sub['id'], current_user.id))['c']
        stats = calculate_stats(attended, conducted, total_semester, sub.get('target_percentage', 80.0) / 100.0)
        summary.append({"subject_id": sub['id'], "subject_name": sub['name'], "total_semester": total_semester, "conducted": conducted, "attended": attended, **stats})
    db.close()
    return jsonify(summary)

@app.route('/api/today', methods=['GET'])
@login_required
def get_today_classes():
    db = get_db()
    classes = db.fetchall("""
        SELECT l.id as log_id, s.name as subject_name, l.status, l.class_date
        FROM attendance_logs l JOIN subjects s ON l.subject_id = s.id
        WHERE l.class_date = ? AND l.user_id = ? ORDER BY l.id ASC
    """, (request.args.get('date', get_ist_now().strftime('%Y-%m-%d')), current_user.id))
    db.close()
    return jsonify(classes)

@app.route('/api/attendance/<int:log_id>', methods=['PATCH'])
@login_required
def update_attendance(log_id):
    if request.json.get('status') not in ['PRESENT', 'ABSENT', 'CANCELLED', 'PENDING']: return jsonify({"error": "Invalid status"}), 400
    db = get_db()
    db.execute("UPDATE attendance_logs SET status = ? WHERE id = ? AND user_id = ?", (request.json.get('status'), log_id, current_user.id))
    db.close()
    return jsonify({"message": "Updated"})

@app.route('/api/attendance/extra', methods=['POST'])
@login_required
def add_extra_class():
    db = get_db()
    db.execute("INSERT INTO attendance_logs (user_id, subject_id, class_date, status) VALUES (?, ?, ?, ?)", 
               (current_user.id, request.json.get('subject_id'), request.json.get('class_date', get_ist_now().strftime('%Y-%m-%d')), request.json.get('status', 'PENDING')))
    db.close()
    return jsonify({"message": "Extra class added"})

@app.route('/api/setup/subject', methods=['POST'])
@login_required
def add_subject():
    db = get_db()
    try:
        db.execute("INSERT INTO subjects (user_id, name, target_percentage) VALUES (?, ?, ?)", (current_user.id, request.json['name'], request.json.get('target_percentage', 80.0)))
        return jsonify({"message": "Subject added"})
    except Exception: return jsonify({"error": "Database error"}), 400
    finally: db.close()

@app.route('/api/setup/schedule', methods=['POST'])
@login_required
def add_schedule():
    db = get_db()
    db.execute_batch([("INSERT INTO schedule (user_id, subject_id, day_of_week) VALUES (?, ?, ?)", (current_user.id, i['subject_id'], i['day_of_week'])) for i in request.json])
    db.close()
    return jsonify({"message": "Schedule added"})

@app.route('/api/setup/holiday', methods=['POST'])
@login_required
def add_holiday():
    start_date = datetime.strptime(request.json['start_date'], '%Y-%m-%d')
    end_date = datetime.strptime(request.json.get('end_date', request.json['start_date']), '%Y-%m-%d')
    db = get_db()
    while start_date <= end_date:
        db.execute("INSERT OR IGNORE INTO holidays (user_id, holiday_date, description) VALUES (?, ?, ?)", (current_user.id, start_date.strftime('%Y-%m-%d'), request.json.get('description', '')))
        start_date += timedelta(days=1)
    db.close()
    return jsonify({"message": "Holidays added"})

@app.route('/api/generate-semester', methods=['POST'])
@login_required
def generate_semester():
    start_date = datetime.strptime(request.json['start_date'], '%Y-%m-%d').date()
    end_date = datetime.strptime(request.json['end_date'], '%Y-%m-%d').date()
    db = get_db()
    
    db.execute("DELETE FROM attendance_logs WHERE class_date BETWEEN ? AND ? AND status = 'PENDING' AND user_id = ?", (request.json['start_date'], request.json['end_date'], current_user.id))
    schedules = db.fetchall("SELECT subject_id, day_of_week FROM schedule WHERE user_id = ?", (current_user.id,))
    blackout_dates = {r['holiday_date'] for r in db.fetchall("SELECT holiday_date FROM holidays WHERE user_id = ?", (current_user.id,))}
    
    logs_to_insert = []
    while start_date <= end_date:
        d_str = start_date.strftime('%Y-%m-%d')
        if d_str not in blackout_dates:
            for s in schedules:
                if s['day_of_week'] == start_date.weekday():
                    logs_to_insert.append((current_user.id, s['subject_id'], d_str, 'PENDING'))
        start_date += timedelta(days=1)
        
    if logs_to_insert:
        db.execute_batch([("INSERT INTO attendance_logs (user_id, subject_id, class_date, status) VALUES (?, ?, ?, ?)", log) for log in logs_to_insert])
    db.close()
    return jsonify({"message": "Semester generated"})

@app.route('/api/history/<int:subject_id>', methods=['GET'])
@login_required
def get_subject_history(subject_id):
    db = get_db()
    logs = db.fetchall("SELECT id as log_id, class_date, status FROM attendance_logs WHERE subject_id = ? AND user_id = ? AND class_date <= ? ORDER BY class_date DESC", (subject_id, current_user.id, get_ist_now().strftime('%Y-%m-%d')))
    db.close()
    return jsonify(logs)

@app.route('/api/setup/reset-database', methods=['POST'])
@login_required
def reset_database():
    db = get_db()
    # ONLY deletes the currently logged-in user's data
    db.execute("DELETE FROM attendance_logs WHERE user_id = ?", (current_user.id,))
    db.execute("DELETE FROM holidays WHERE user_id = ?", (current_user.id,))
    db.execute("DELETE FROM schedule WHERE user_id = ?", (current_user.id,))
    db.execute("DELETE FROM subjects WHERE user_id = ?", (current_user.id,))
    db.close()
    return jsonify({"message": "Your personal database records have been wiped."})

if __name__ == '__main__':
    app.run(debug=True, port=5000)