-- Campus Health-Center Decision Support Database Schema
-- SQLite Normalized Schema with 9 relational tables

PRAGMA foreign_keys = ON;

-- 1. Patients Table
CREATE TABLE IF NOT EXISTS Patients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_code TEXT UNIQUE NOT NULL,
    full_name TEXT NOT NULL,
    age INTEGER NOT NULL CHECK(age >= 0 AND age <= 130),
    gender TEXT,
    contact TEXT,
    department TEXT DEFAULT 'General Medicine & Primary Care',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Symptom_Reports Table
CREATE TABLE IF NOT EXISTS Symptom_Reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER NOT NULL,
    symptoms_json TEXT NOT NULL,
    additional_description TEXT,
    duration_days REAL NOT NULL CHECK(duration_days >= 0),
    pain_scale INTEGER DEFAULT 0 CHECK(pain_scale >= 0 AND pain_scale <= 10),
    inferred_severity INTEGER DEFAULT 1 CHECK(inferred_severity >= 0 AND inferred_severity <= 10),
    temperature_c REAL,
    respiratory_distress BOOLEAN DEFAULT 0,
    altered_consciousness BOOLEAN DEFAULT 0,
    severe_chest_pain BOOLEAN DEFAULT 0,
    uncontrolled_bleeding BOOLEAN DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id) REFERENCES Patients(id) ON DELETE CASCADE
);

-- 3. Rule_Definitions Table
CREATE TABLE IF NOT EXISTS Rule_Definitions (
    rule_id TEXT PRIMARY KEY,
    category TEXT NOT NULL,
    name TEXT NOT NULL,
    condition_description TEXT NOT NULL,
    action_priority TEXT NOT NULL,
    clinical_rationale TEXT NOT NULL,
    source_protocol TEXT NOT NULL,
    is_active BOOLEAN DEFAULT 1
);

-- 4. Triggered_Rules Table
CREATE TABLE IF NOT EXISTS Triggered_Rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER NOT NULL,
    rule_id TEXT NOT NULL,
    trigger_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    explanation TEXT NOT NULL,
    facts_matched_json TEXT,
    is_conflict_winner BOOLEAN DEFAULT 0,
    FOREIGN KEY (patient_id) REFERENCES Patients(id) ON DELETE CASCADE,
    FOREIGN KEY (rule_id) REFERENCES Rule_Definitions(rule_id)
);

-- 5. Appointments Table
CREATE TABLE IF NOT EXISTS Appointments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER NOT NULL,
    slot_start TEXT NOT NULL,
    slot_end TEXT NOT NULL,
    provider_id TEXT NOT NULL,
    provider_name TEXT NOT NULL,
    department TEXT DEFAULT 'General Medicine & Primary Care',
    priority_category TEXT NOT NULL,
    status TEXT DEFAULT 'SCHEDULED' CHECK(status IN ('SCHEDULED', 'IN_PROGRESS', 'COMPLETED', 'ESCALATED_ER', 'CANCELLED')),
    algorithm TEXT NOT NULL CHECK(algorithm IN ('PRIORITY_AGENT', 'FCFS')),
    queue_position INTEGER,
    estimated_wait_minutes REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id) REFERENCES Patients(id) ON DELETE CASCADE
);

-- 6. Scheduling_History Table
CREATE TABLE IF NOT EXISTS Scheduling_History (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER NOT NULL,
    action TEXT NOT NULL,
    old_slot TEXT,
    new_slot TEXT,
    old_priority TEXT,
    new_priority TEXT,
    reason TEXT NOT NULL,
    changed_by TEXT NOT NULL,
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id) REFERENCES Patients(id) ON DELETE CASCADE
);

-- 7. RAG_Documents Table
CREATE TABLE IF NOT EXISTS RAG_Documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    source_org TEXT NOT NULL,
    filename TEXT NOT NULL,
    total_chunks INTEGER DEFAULT 0,
    content_hash TEXT,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 8. Admin_Users Table
CREATE TABLE IF NOT EXISTS Admin_Users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    full_name TEXT NOT NULL,
    role TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    is_active BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 9. Audit_Logs Table
CREATE TABLE IF NOT EXISTS Audit_Logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    admin_user TEXT NOT NULL,
    action_type TEXT NOT NULL,
    patient_id INTEGER,
    details TEXT NOT NULL,
    ip_address TEXT DEFAULT '127.0.0.1',
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id) REFERENCES Patients(id) ON DELETE SET NULL
);

-- Indexes for optimal lookup performance
CREATE INDEX IF NOT EXISTS idx_patients_code ON Patients(patient_code);
CREATE INDEX IF NOT EXISTS idx_symptom_patient ON Symptom_Reports(patient_id);
CREATE INDEX IF NOT EXISTS idx_triggered_patient ON Triggered_Rules(patient_id);
CREATE INDEX IF NOT EXISTS idx_appointments_patient ON Appointments(patient_id);
CREATE INDEX IF NOT EXISTS idx_appointments_status ON Appointments(status);
CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON Audit_Logs(timestamp);
