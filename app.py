'''
from flask import Flask, request, jsonify, render_template
import sqlite3
from datetime import datetime, timedelta

app = Flask(__name__, static_folder='frontend', template_folder='frontend')
DATABASE = 'database.db'

def get_db():
    conn = sqlite3.connect(DATABASE, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn

# Helper: Attendance calculation logic with Semester Boundary Checks
def calculate_stats(attended, conducted, total_semester, target_pct=0.80):
    if conducted == 0:
        return {
            "percentage": 100.0,
            "status": "NO_CLASSES",
            "message": "No classes held yet"
        }
    
    current_pct = attended / conducted
    
    if current_pct >= target_pct:
        # Number of future consecutive classes you can skip while staying >= target
        skippable = int((attended - (target_pct * conducted)) / target_pct)
        return {
            "percentage": round(current_pct * 100, 1),
            "status": "SAFE",
            "message": f"Safe to skip next {skippable} class(es)" if skippable > 0 else "On track (80% boundary)"
        }
    else:
        # Number of future consecutive classes required to reach target
        required = int(-(-((target_pct * conducted) - attended) // (1 - target_pct)))
        remaining_in_semester = max(0, total_semester - conducted)
        
        # If total semester logs are generated and required > remaining, it's impossible
        if total_semester > 0 and required > remaining_in_semester:
            max_possible_attended = attended + remaining_in_semester
            max_possible_pct = round((max_possible_attended / total_semester) * 100, 1)
            return {
                "percentage": round(current_pct * 100, 1),
                "status": "CRITICAL",
                "message": f"Cannot reach {int(target_pct*100)}%! Max possible: {max_possible_pct}%"
            }
        
        return {
            "percentage": round(current_pct * 100, 1),
            "status": "CRITICAL",
            "message": f"Must attend next {required} class(es)"
        }

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/dashboard', methods=['GET'])
def get_dashboard():
    conn = get_db()
    cursor = conn.cursor()

    subjects = cursor.execute("SELECT * FROM subjects").fetchall()
    summary = []

    for sub in subjects:
        total_semester = cursor.execute("""
            SELECT COUNT(*) FROM attendance_logs 
            WHERE subject_id = ? AND status != 'CANCELLED'
        """, (sub['id'],)).fetchone()[0]

        conducted = cursor.execute("""
            SELECT COUNT(*) FROM attendance_logs 
            WHERE subject_id = ? AND status IN ('PRESENT', 'ABSENT')
        """, (sub['id'],)).fetchone()[0]

        attended = cursor.execute("""
            SELECT COUNT(*) FROM attendance_logs 
            WHERE subject_id = ? AND status = 'PRESENT'
        """, (sub['id'],)).fetchone()[0]

        target = sub['target_percentage'] / 100.0
        stats = calculate_stats(attended, conducted, total_semester, target)

        summary.append({
            "subject_id": sub['id'],
            "subject_name": sub['name'],
            "total_semester": total_semester,
            "conducted": conducted,
            "attended": attended,
            "percentage": stats["percentage"],
            "status": stats["status"],
            "message": stats["message"]
        })

    conn.close()
    return jsonify(summary)

@app.route('/api/today', methods=['GET'])
def get_today_classes():
    today_str = datetime.now().strftime('%Y-%m-%d')
    conn = get_db()
    cursor = conn.cursor()

    classes = cursor.execute("""
        SELECT l.id as log_id, s.name as subject_name, l.status, l.class_date
        FROM attendance_logs l
        JOIN subjects s ON l.subject_id = s.id
        WHERE l.class_date = ?
        ORDER BY l.id ASC
    """, (today_str,)).fetchall()

    conn.close()
    return jsonify([dict(row) for row in classes])

@app.route('/api/attendance/<int:log_id>', methods=['PATCH'])
def update_attendance(log_id):
    data = request.json
    new_status = data.get('status')

    if new_status not in ['PRESENT', 'ABSENT', 'CANCELLED', 'PENDING']:
        return jsonify({"error": "Invalid status"}), 400

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE attendance_logs SET status = ? WHERE id = ?", (new_status, log_id))
    conn.commit()
    conn.close()

    return jsonify({"message": "Status updated successfully"})

@app.route('/api/setup/subject', methods=['POST'])
def add_subject():
    data = request.json
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO subjects (name, target_percentage) VALUES (?, ?)", 
                       (data['name'], data.get('target_percentage', 80.0)))
        conn.commit()
        return jsonify({"message": "Subject added successfully"}), 201
    except sqlite3.IntegrityError:
        return jsonify({"error": "Subject already exists"}), 400
    finally:
        conn.close()

@app.route('/api/setup/schedule', methods=['POST'])
def add_schedule():
    data = request.json
    conn = get_db()
    cursor = conn.cursor()
    try:
        for item in data:
            cursor.execute("INSERT INTO schedule (subject_id, day_of_week) VALUES (?, ?)", 
                           (item['subject_id'], item['day_of_week']))
        conn.commit()
        return jsonify({"message": "Schedule added successfully"}), 201
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 400
    finally:
        conn.close()

@app.route('/api/setup/holiday', methods=['POST'])
def add_holiday():
    data = request.json
    start_date = datetime.strptime(data['start_date'], '%Y-%m-%d')
    end_date = datetime.strptime(data.get('end_date', data['start_date']), '%Y-%m-%d')
    description = data.get('description', '')

    conn = get_db()
    cursor = conn.cursor()
    curr_date = start_date

    try:
        while curr_date <= end_date:
            date_str = curr_date.strftime('%Y-%m-%d')
            cursor.execute("INSERT OR IGNORE INTO holidays (holiday_date, description) VALUES (?, ?)", 
                           (date_str, description))
            curr_date += timedelta(days=1)
        conn.commit()
        return jsonify({"message": "Holiday(s) added successfully"}), 201
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 400
    finally:
        conn.close()

@app.route('/api/generate-semester', methods=['POST'])
def generate_semester():
    data = request.json
    start_date = datetime.strptime(data['start_date'], '%Y-%m-%d')
    end_date = datetime.strptime(data['end_date'], '%Y-%m-%d')

    conn = get_db()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            DELETE FROM attendance_logs 
            WHERE class_date BETWEEN ? AND ? AND status = 'PENDING'
        """, (data['start_date'], data['end_date']))

        schedules = cursor.execute("SELECT subject_id, day_of_week FROM schedule").fetchall()
        holidays = {row['holiday_date'] for row in cursor.execute("SELECT holiday_date FROM holidays").fetchall()}

        curr_date = start_date
        logs_to_insert = []

        while curr_date <= end_date:
            date_str = curr_date.strftime('%Y-%m-%d')
            day_of_week = curr_date.weekday()

            if date_str not in holidays:
                for sched in schedules:
                    if sched['day_of_week'] == day_of_week:
                        logs_to_insert.append((sched['subject_id'], date_str, 'PENDING'))
            
            curr_date += timedelta(days=1)

        cursor.executemany("""
            INSERT INTO attendance_logs (subject_id, class_date, status)
            VALUES (?, ?, ?)
        """, logs_to_insert)

        conn.commit()
        return jsonify({"message": f"Generated schedules from {data['start_date']} to {data['end_date']}"})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

if __name__ == '__main__':
    app.run(debug=True, port=5000)
'''



#WITH EXTRA CLASSES FEATURE
'''
from flask import Flask, request, jsonify, render_template
import sqlite3
import os
from datetime import datetime, timedelta

app = Flask(__name__, static_folder='frontend', template_folder='frontend')
DATABASE = 'database.db'

def get_db():
    conn = sqlite3.connect(DATABASE, timeout=10)
    conn.row_factory = sqlite3.Row
    
    # Auto-initialize database tables if missing
    cursor = conn.cursor()
    cursor.execute("SELECT count(name) FROM sqlite_master WHERE type='table' AND name='subjects'")
    if cursor.fetchone()[0] == 0:
        if os.path.exists('schema.sql'):
            with open('schema.sql', 'r') as f:
                conn.executescript(f.read())
            conn.commit()
            
    return conn

# Attendance calculation logic with Semester Boundary Checks
def calculate_stats(attended, conducted, total_semester, target_pct=0.80):
    if conducted == 0:
        return {
            "percentage": 100.0,
            "status": "NO_CLASSES",
            "message": "No classes held yet"
        }
    
    current_pct = attended / conducted
    
    if current_pct >= target_pct:
        skippable = int((attended - (target_pct * conducted)) / target_pct)
        return {
            "percentage": round(current_pct * 100, 1),
            "status": "SAFE",
            "message": f"Safe to skip next {skippable} class(es)" if skippable > 0 else "On track (80% boundary)"
        }
    else:
        required = int(-(-((target_pct * conducted) - attended) // (1 - target_pct)))
        remaining_in_semester = max(0, total_semester - conducted)
        
        if total_semester > 0 and required > remaining_in_semester:
            max_possible_attended = attended + remaining_in_semester
            max_possible_pct = round((max_possible_attended / total_semester) * 100, 1)
            return {
                "percentage": round(current_pct * 100, 1),
                "status": "CRITICAL",
                "message": f"Cannot reach {int(target_pct*100)}%! Max possible: {max_possible_pct}%"
            }
        
        return {
            "percentage": round(current_pct * 100, 1),
            "status": "CRITICAL",
            "message": f"Must attend next {required} class(es)"
        }

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/dashboard', methods=['GET'])
def get_dashboard():
    conn = get_db()
    cursor = conn.cursor()

    subjects = cursor.execute("SELECT * FROM subjects").fetchall()
    summary = []

    for sub in subjects:
        total_semester = cursor.execute("""
            SELECT COUNT(*) FROM attendance_logs 
            WHERE subject_id = ? AND status != 'CANCELLED'
        """, (sub['id'],)).fetchone()[0]

        conducted = cursor.execute("""
            SELECT COUNT(*) FROM attendance_logs 
            WHERE subject_id = ? AND status IN ('PRESENT', 'ABSENT')
        """, (sub['id'],)).fetchone()[0]

        attended = cursor.execute("""
            SELECT COUNT(*) FROM attendance_logs 
            WHERE subject_id = ? AND status = 'PRESENT'
        """, (sub['id'],)).fetchone()[0]

        target = sub['target_percentage'] / 100.0
        stats = calculate_stats(attended, conducted, total_semester, target)

        summary.append({
            "subject_id": sub['id'],
            "subject_name": sub['name'],
            "total_semester": total_semester,
            "conducted": conducted,
            "attended": attended,
            "percentage": stats["percentage"],
            "status": stats["status"],
            "message": stats["message"]
        })

    conn.close()
    return jsonify(summary)

@app.route('/api/today', methods=['GET'])
def get_today_classes():
    today_str = datetime.now().strftime('%Y-%m-%d')
    conn = get_db()
    cursor = conn.cursor()

    classes = cursor.execute("""
        SELECT l.id as log_id, s.name as subject_name, l.status, l.class_date
        FROM attendance_logs l
        JOIN subjects s ON l.subject_id = s.id
        WHERE l.class_date = ?
        ORDER BY l.id ASC
    """, (today_str,)).fetchall()

    conn.close()
    return jsonify([dict(row) for row in classes])

@app.route('/api/attendance/<int:log_id>', methods=['PATCH'])
def update_attendance(log_id):
    data = request.json
    new_status = data.get('status')

    if new_status not in ['PRESENT', 'ABSENT', 'CANCELLED', 'PENDING']:
        return jsonify({"error": "Invalid status"}), 400

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE attendance_logs SET status = ? WHERE id = ?", (new_status, log_id))
    conn.commit()
    conn.close()

    return jsonify({"message": "Status updated successfully"})

@app.route('/api/attendance/extra', methods=['POST'])
def add_extra_class():
    data = request.json
    subject_id = data.get('subject_id')
    class_date = data.get('class_date', datetime.now().strftime('%Y-%m-%d'))
    status = data.get('status', 'PENDING')

    if not subject_id:
        return jsonify({"error": "Subject is required"}), 400

    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO attendance_logs (subject_id, class_date, status)
            VALUES (?, ?, ?)
        """, (subject_id, class_date, status))
        conn.commit()
        return jsonify({"message": "Extra class added successfully!"}), 201
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

@app.route('/api/setup/subject', methods=['POST'])
def add_subject():
    data = request.json
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO subjects (name, target_percentage) VALUES (?, ?)", 
                       (data['name'], data.get('target_percentage', 80.0)))
        conn.commit()
        return jsonify({"message": "Subject added successfully"}), 201
    except sqlite3.IntegrityError:
        return jsonify({"error": "Subject already exists"}), 400
    finally:
        conn.close()

@app.route('/api/setup/schedule', methods=['POST'])
def add_schedule():
    data = request.json
    conn = get_db()
    cursor = conn.cursor()
    try:
        for item in data:
            cursor.execute("INSERT INTO schedule (subject_id, day_of_week) VALUES (?, ?)", 
                           (item['subject_id'], item['day_of_week']))
        conn.commit()
        return jsonify({"message": "Schedule added successfully"}), 201
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 400
    finally:
        conn.close()

@app.route('/api/setup/holiday', methods=['POST'])
def add_holiday():
    data = request.json
    start_date = datetime.strptime(data['start_date'], '%Y-%m-%d')
    end_date = datetime.strptime(data.get('end_date', data['start_date']), '%Y-%m-%d')
    description = data.get('description', '')

    conn = get_db()
    cursor = conn.cursor()
    curr_date = start_date

    try:
        while curr_date <= end_date:
            date_str = curr_date.strftime('%Y-%m-%d')
            cursor.execute("INSERT OR IGNORE INTO holidays (holiday_date, description) VALUES (?, ?)", 
                           (date_str, description))
            curr_date += timedelta(days=1)
        conn.commit()
        return jsonify({"message": "Holiday(s) added successfully"}), 201
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 400
    finally:
        conn.close()

@app.route('/api/generate-semester', methods=['POST'])
def generate_semester():
    data = request.json
    start_date = datetime.strptime(data['start_date'], '%Y-%m-%d')
    end_date = datetime.strptime(data['end_date'], '%Y-%m-%d')

    conn = get_db()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            DELETE FROM attendance_logs 
            WHERE class_date BETWEEN ? AND ? AND status = 'PENDING'
        """, (data['start_date'], data['end_date']))

        schedules = cursor.execute("SELECT subject_id, day_of_week FROM schedule").fetchall()
        holidays = {row['holiday_date'] for row in cursor.execute("SELECT holiday_date FROM holidays").fetchall()}

        curr_date = start_date
        logs_to_insert = []

        while curr_date <= end_date:
            date_str = curr_date.strftime('%Y-%m-%d')
            day_of_week = curr_date.weekday()

            if date_str not in holidays:
                for sched in schedules:
                    if sched['day_of_week'] == day_of_week:
                        logs_to_insert.append((sched['subject_id'], date_str, 'PENDING'))
            
            curr_date += timedelta(days=1)

        cursor.executemany("""
            INSERT INTO attendance_logs (subject_id, class_date, status)
            VALUES (?, ?, ?)
        """, logs_to_insert)

        conn.commit()
        return jsonify({"message": f"Generated schedules from {data['start_date']} to {data['end_date']}"})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

@app.route('/api/setup/reset-database', methods=['POST'])
def reset_database():
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("DROP TABLE IF EXISTS attendance_logs")
        cursor.execute("DROP TABLE IF EXISTS holidays")
        cursor.execute("DROP TABLE IF EXISTS schedule")
        cursor.execute("DROP TABLE IF EXISTS subjects")
        
        if os.path.exists('schema.sql'):
            with open('schema.sql', 'r') as f:
                cursor.executescript(f.read())
            conn.commit()
            return jsonify({"message": "Database successfully reset!"}), 200
        return jsonify({"error": "schema.sql missing"}), 500
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

if __name__ == '__main__':
    app.run(debug=True, port=5000)
'''


# 
from flask import Flask, request, jsonify, render_template
import sqlite3
import requests
import os
from datetime import datetime, timedelta, timezone

def get_ist_now():
    """Forces the server time to Asia/Kolkata (UTC + 5:30)"""
    ist_offset = timedelta(hours=5, minutes=30)
    return datetime.now(timezone.utc) + ist_offset

app = Flask(__name__, static_folder='frontend', template_folder='frontend')

TURSO_DATABASE_URL = os.environ.get("TURSO_DATABASE_URL")
TURSO_AUTH_TOKEN = os.environ.get("TURSO_AUTH_TOKEN")

class TursoHTTPDatabase:
    """Wrapper to run SQL queries over Turso's HTTP Pipeline API"""
    def __init__(self, url, token):
        clean_url = url.strip().replace("libsql://", "https://")
        if not clean_url.endswith("/v2/pipeline"):
            clean_url = clean_url.rstrip("/") + "/v2/pipeline"
        self.url = clean_url
        self.headers = {
            "Authorization": f"Bearer {token.strip()}",
            "Content-Type": "application/json"
        }

    def _format_args(self, args):
        formatted_args = []
        for arg in args:
            if arg is None:
                formatted_args.append({"type": "null"})
            elif isinstance(arg, int):
                formatted_args.append({"type": "integer", "value": str(arg)})
            elif isinstance(arg, float):
                formatted_args.append({"type": "float", "value": arg})
            else:
                formatted_args.append({"type": "text", "value": str(arg)})
        return formatted_args

    def execute_pipeline(self, statements):
        """Executes multiple SQL statements in a SINGLE batch HTTP request"""
        requests_payload = []
        for sql, args in statements:
            requests_payload.append({
                "type": "execute",
                "stmt": {
                    "sql": sql,
                    "args": self._format_args(args or [])
                }
            })
        requests_payload.append({"type": "close"})

        response = requests.post(self.url, json={"requests": requests_payload}, headers=self.headers, timeout=30)
        if response.status_code != 200:
            raise Exception(f"Turso API Error {response.status_code}: {response.text}")
        return response.json()

    def execute_raw(self, sql, args=None):
        data = self.execute_pipeline([(sql, args or [])])
        results = data["results"][0]
        if results["type"] == "error":
            raise Exception(f"Turso Query Error: {results['error']['message']}")
        return results.get("response", {}).get("result", {})

    def fetchall(self, sql, args=None):
        res = self.execute_raw(sql, args)
        cols = [c["name"] for c in res.get("cols", [])]
        rows = []
        for r in res.get("rows", []):
            row_dict = {}
            for idx, col_name in enumerate(cols):
                val = r[idx]["value"] if r[idx]["type"] != "null" else None
                if r[idx]["type"] == "integer" and val is not None:
                    val = int(val)
                elif r[idx]["type"] == "float" and val is not None:
                    val = float(val)
                row_dict[col_name] = val
            rows.append(row_dict)
        return rows

    def fetchone(self, sql, args=None):
        rows = self.fetchall(sql, args)
        return rows[0] if rows else None

    def execute(self, sql, args=None):
        self.execute_raw(sql, args)

class DBConnection:
    """Unified wrapper handling both Local SQLite and Remote Turso HTTP"""
    def __init__(self):
        if TURSO_DATABASE_URL and TURSO_AUTH_TOKEN:
            self.mode = "TURSO"
            self.turso = TursoHTTPDatabase(TURSO_DATABASE_URL, TURSO_AUTH_TOKEN)
        else:
            self.mode = "SQLITE"
            self.conn = sqlite3.connect("database.db", timeout=10)
            self.conn.row_factory = sqlite3.Row

    def fetchall(self, sql, args=None):
        if args is None: args = ()
        if self.mode == "TURSO":
            return self.turso.fetchall(sql, args)
        else:
            cur = self.conn.cursor()
            rows = cur.execute(sql, args).fetchall()
            return [dict(r) for r in rows]

    def fetchone(self, sql, args=None):
        if args is None: args = ()
        if self.mode == "TURSO":
            return self.turso.fetchone(sql, args)
        else:
            cur = self.conn.cursor()
            row = cur.execute(sql, args).fetchone()
            return dict(row) if row else None

    def execute(self, sql, args=None):
        if args is None: args = ()
        if self.mode == "TURSO":
            self.turso.execute(sql, args)
        else:
            cur = self.conn.cursor()
            cur.execute(sql, args)
            self.conn.commit()

    def execute_batch(self, statements):
        """Batch execution helper"""
        if self.mode == "TURSO":
            self.turso.execute_pipeline(statements)
        else:
            cur = self.conn.cursor()
            for sql, args in statements:
                cur.execute(sql, args)
            self.conn.commit()

    def close(self):
        if self.mode == "SQLITE":
            self.conn.close()

def get_db():
    db = DBConnection()
    try:
        tbl = db.fetchone("SELECT name FROM sqlite_master WHERE type='table' AND name='subjects'")
        if not tbl:
            db.execute("""
                CREATE TABLE IF NOT EXISTS subjects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    target_percentage REAL DEFAULT 80.0
                );
            """)
            db.execute("""
                CREATE TABLE IF NOT EXISTS schedule (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    subject_id INTEGER NOT NULL,
                    day_of_week INTEGER NOT NULL
                );
            """)
            db.execute("""
                CREATE TABLE IF NOT EXISTS holidays (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    holiday_date TEXT NOT NULL UNIQUE,
                    description TEXT
                );
            """)
            db.execute("""
                CREATE TABLE IF NOT EXISTS attendance_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    subject_id INTEGER NOT NULL,
                    class_date TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'PENDING'
                );
            """)
    except Exception as e:
        print(f"Table initialization note: {e}")
    return db

def calculate_stats(attended, conducted, total_semester, target_pct=0.80):
    if conducted == 0:
        return {
            "percentage": 100.0,
            "status": "NO_CLASSES",
            "message": "No classes held yet"
        }
    
    current_pct = attended / conducted
    
    if current_pct >= target_pct:
        skippable = int((attended - (target_pct * conducted)) / target_pct)
        return {
            "percentage": round(current_pct * 100, 1),
            "status": "SAFE",
            "message": f"Safe to skip next {skippable} class(es)" if skippable > 0 else "On track (80% boundary)"
        }
    else:
        required = int(-(-((target_pct * conducted) - attended) // (1 - target_pct)))
        remaining_in_semester = max(0, total_semester - conducted)
        
        if total_semester > 0 and required > remaining_in_semester:
            max_possible_attended = attended + remaining_in_semester
            max_possible_pct = round((max_possible_attended / total_semester) * 100, 1)
            return {
                "percentage": round(current_pct * 100, 1),
                "status": "CRITICAL",
                "message": f"Cannot reach {int(target_pct*100)}%! Max possible: {max_possible_pct}%"
            }
        
        return {
            "percentage": round(current_pct * 100, 1),
            "status": "CRITICAL",
            "message": f"Must attend next {required} class(es)"
        }

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/dashboard', methods=['GET'])
def get_dashboard():
    db = get_db()
    subjects = db.fetchall("SELECT * FROM subjects")
    summary = []

    for sub in subjects:
        sub_id = sub['id']
        
        t_res = db.fetchone("SELECT COUNT(*) as count FROM attendance_logs WHERE subject_id = ? AND status != 'CANCELLED'", (sub_id,))
        total_semester = t_res['count'] if t_res else 0

        c_res = db.fetchone("SELECT COUNT(*) as count FROM attendance_logs WHERE subject_id = ? AND status IN ('PRESENT', 'ABSENT')", (sub_id,))
        conducted = c_res['count'] if c_res else 0

        a_res = db.fetchone("SELECT COUNT(*) as count FROM attendance_logs WHERE subject_id = ? AND status = 'PRESENT'", (sub_id,))
        attended = a_res['count'] if a_res else 0

        target = sub.get('target_percentage', 80.0) / 100.0
        stats = calculate_stats(attended, conducted, total_semester, target)

        summary.append({
            "subject_id": sub_id,
            "subject_name": sub['name'],
            "total_semester": total_semester,
            "conducted": conducted,
            "attended": attended,
            "percentage": stats["percentage"],
            "status": stats["status"],
            "message": stats["message"]
        })

    db.close()
    return jsonify(summary)

@app.route('/api/today', methods=['GET'])
def get_today_classes():
    # Accepts an optional query param like /api/today?date=2026-07-27
    target_date = request.args.get('date', get_ist_now().strftime('%Y-%m-%d'))
    db = get_db()

    classes = db.fetchall("""
        SELECT l.id as log_id, s.name as subject_name, l.status, l.class_date
        FROM attendance_logs l
        JOIN subjects s ON l.subject_id = s.id
        WHERE l.class_date = ?
        ORDER BY l.id ASC
    """, (target_date,))

    db.close()
    return jsonify(classes)

@app.route('/api/attendance/<int:log_id>', methods=['PATCH'])
def update_attendance(log_id):
    data = request.json
    new_status = data.get('status')

    if new_status not in ['PRESENT', 'ABSENT', 'CANCELLED', 'PENDING']:
        return jsonify({"error": "Invalid status"}), 400

    db = get_db()
    db.execute("UPDATE attendance_logs SET status = ? WHERE id = ?", (new_status, log_id))
    db.close()

    return jsonify({"message": "Status updated successfully"})

@app.route('/api/attendance/extra', methods=['POST'])
def add_extra_class():
    data = request.json
    subject_id = data.get('subject_id')
    class_date = data.get('class_date', get_ist_now().strftime('%Y-%m-%d'))
    status = data.get('status', 'PENDING')

    if not subject_id:
        return jsonify({"error": "Subject is required"}), 400

    db = get_db()
    try:
        db.execute("""
            INSERT INTO attendance_logs (subject_id, class_date, status)
            VALUES (?, ?, ?)
        """, (subject_id, class_date, status))
        return jsonify({"message": "Extra class added successfully!"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()

@app.route('/api/setup/subject', methods=['POST'])
def add_subject():
    data = request.json
    db = get_db()
    try:
        db.execute("INSERT INTO subjects (name, target_percentage) VALUES (?, ?)", 
                   (data['name'], data.get('target_percentage', 80.0)))
        return jsonify({"message": "Subject added successfully"}), 201
    except Exception as e:
        return jsonify({"error": "Subject already exists or database error"}), 400
    finally:
        db.close()

@app.route('/api/setup/schedule', methods=['POST'])
def add_schedule():
    data = request.json
    db = get_db()
    try:
        for item in data:
            db.execute("INSERT INTO schedule (subject_id, day_of_week) VALUES (?, ?)", 
                       (item['subject_id'], item['day_of_week']))
        return jsonify({"message": "Schedule added successfully"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    finally:
        db.close()

@app.route('/api/setup/holiday', methods=['POST'])
def add_holiday():
    data = request.json
    start_date = datetime.strptime(data['start_date'], '%Y-%m-%d')
    end_date = datetime.strptime(data.get('end_date', data['start_date']), '%Y-%m-%d')
    description = data.get('description', '')

    db = get_db()
    curr_date = start_date

    try:
        while curr_date <= end_date:
            date_str = curr_date.strftime('%Y-%m-%d')
            db.execute("INSERT OR IGNORE INTO holidays (holiday_date, description) VALUES (?, ?)", 
                       (date_str, description))
            curr_date += timedelta(days=1)
        return jsonify({"message": "Holiday(s) added successfully"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    finally:
        db.close()

@app.route('/api/generate-semester', methods=['POST'])
def generate_semester():
    data = request.json
    start_date = datetime.strptime(data['start_date'], '%Y-%m-%d').date()
    end_date = datetime.strptime(data['end_date'], '%Y-%m-%d').date()
    
    db = get_db()
    
    try:
        # 1. Clean up existing PENDING classes in this range to prevent duplicates
        db.execute("""
            DELETE FROM attendance_logs 
            WHERE class_date BETWEEN ? AND ? AND status = 'PENDING'
        """, (data['start_date'], data['end_date']))

        # 2. Fetch required data for generation
        schedules = db.fetchall("SELECT subject_id, day_of_week FROM schedule")
        # Fetch all blackout dates directly from the schema
        holidays_data = db.fetchall("SELECT holiday_date FROM holidays")
        blackout_dates = {row['holiday_date'] for row in holidays_data}
        
        current_date = start_date
        logs_to_insert = []
        
        # 3. Loop through every date in the semester
        while current_date <= end_date:
            current_date_str = current_date.strftime('%Y-%m-%d')
            day_of_week = current_date.weekday()
            
            # 4. If it is NOT an exam/holiday, schedule the classes
            if current_date_str not in blackout_dates:
                for sched in schedules:
                    if sched['day_of_week'] == day_of_week:
                        logs_to_insert.append((sched['subject_id'], current_date_str, 'PENDING'))
            
            current_date += timedelta(days=1)
            
        # 5. Batch insert all generated classes
        if logs_to_insert:
            db.execute_batch([
                ("INSERT INTO attendance_logs (subject_id, class_date, status) VALUES (?, ?, ?)", log) 
                for log in logs_to_insert
            ])

        return jsonify({"message": f"Generated schedules from {data['start_date']} to {data['end_date']}."})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()

@app.route('/api/setup/reset-database', methods=['POST'])
def reset_database():
    db = get_db()
    try:
        db.execute("DROP TABLE IF EXISTS attendance_logs")
        db.execute("DROP TABLE IF EXISTS holidays")
        db.execute("DROP TABLE IF EXISTS schedule")
        db.execute("DROP TABLE IF EXISTS subjects")
        get_db()
        return jsonify({"message": "Database reset successful!"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()

@app.route('/api/history/<int:subject_id>', methods=['GET'])
def get_subject_history(subject_id):
    today_str = get_ist_now().strftime('%Y-%m-%d')
    db = get_db()
    
    # Fetch all logs for the selected subject up to today, sorted newest first
    logs = db.fetchall("""
        SELECT id as log_id, class_date, status 
        FROM attendance_logs 
        WHERE subject_id = ? AND class_date <= ?
        ORDER BY class_date DESC
    """, (subject_id, today_str))
    
    db.close()
    return jsonify(logs)


if __name__ == '__main__':
    app.run(debug=True, port=5000)