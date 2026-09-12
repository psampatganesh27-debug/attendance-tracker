-- Disable foreign key checks briefly to allow clean table resets during testing
PRAGMA foreign_keys = OFF;

DROP TABLE IF EXISTS attendance_logs;
DROP TABLE IF EXISTS holidays;
DROP TABLE IF EXISTS schedule;
DROP TABLE IF EXISTS subjects;

PRAGMA foreign_keys = ON;

-- 1. Subjects Table
CREATE TABLE subjects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    target_percentage REAL DEFAULT 80.0
);

-- 2. Weekly Timetable Schedule Table
-- day_of_week mapping: 0 = Monday, 1 = Tuesday, 2 = Wednesday, 3 = Thursday, 4 = Friday, 5 = Saturday, 6 = Sunday
CREATE TABLE schedule (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_id INTEGER NOT NULL,
    day_of_week INTEGER NOT NULL CHECK(day_of_week BETWEEN 0 AND 6),
    FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE
);

-- 3. Holidays Table
CREATE TABLE holidays (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    holiday_date TEXT NOT NULL UNIQUE, -- Stored as 'YYYY-MM-DD'
    description TEXT
);

-- 4. Daily Attendance Logs Table
CREATE TABLE attendance_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_id INTEGER NOT NULL,
    class_date TEXT NOT NULL, -- Stored as 'YYYY-MM-DD'
    status TEXT DEFAULT 'PENDING' CHECK(status IN ('PENDING', 'PRESENT', 'ABSENT', 'CANCELLED')),
    FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE
);