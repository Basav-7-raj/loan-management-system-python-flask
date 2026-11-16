import random
import sqlite3
import os
from datetime import date, timedelta

DB_PATH = os.path.join(os.path.dirname(__file__), "loanpro.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn

def init_db():
    db = get_db()
    db.executescript("""
        CREATE TABLE IF NOT EXISTS borrowers (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            name         TEXT NOT NULL,
            phone        TEXT,
            email        TEXT,
            address      TEXT,
            credit_score INTEGER DEFAULT 700,
            created_at   TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS loans (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            loan_id         TEXT UNIQUE NOT NULL,
            borrower_id     INTEGER NOT NULL REFERENCES borrowers(id) ON DELETE RESTRICT,
            loan_type       TEXT NOT NULL,
            amount          REAL NOT NULL CHECK(amount > 0),
            interest_rate   REAL NOT NULL CHECK(interest_rate >= 0),
            tenure_months   INTEGER NOT NULL CHECK(tenure_months > 0),
            emi             REAL NOT NULL,
            status          TEXT DEFAULT 'Pending' CHECK(status IN ('Pending','Approved','Active','Overdue','Closed','Rejected')),
            amount_paid     REAL DEFAULT 0 CHECK(amount_paid >= 0),
            created_at      TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS payments (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            loan_id      INTEGER NOT NULL REFERENCES loans(id) ON DELETE CASCADE,
            amount       REAL NOT NULL CHECK(amount > 0),
            payment_date TEXT NOT NULL,
            note         TEXT,
            created_at   TEXT DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_loans_borrower ON loans(borrower_id);
        CREATE INDEX IF NOT EXISTS idx_loans_status   ON loans(status);
        CREATE INDEX IF NOT EXISTS idx_payments_loan  ON payments(loan_id);

        CREATE TABLE IF NOT EXISTS branches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            branch_name TEXT,
            city TEXT,
            manager_name TEXT
        );

        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );
    """)

    count = db.execute("SELECT COUNT(*) FROM borrowers").fetchone()[0]
    if count == 0:
        branches = [("Central Finance Hub","Bengaluru","Raghavendra"),("North Region","Mysuru","Priya N"),("Corporate Banking","Hubli","Kiran S")]
        db.executemany("INSERT INTO branches (branch_name, city, manager_name) VALUES (?,?,?)", branches)

        first_names=["Arjun","Kiran","Manoj","Rahul","Sneha","Divya","Asha","Naveen","Tejas","Ritu","Sanjay","Lakshmi"]
        cities=["Bengaluru","Mysuru","Hubli","Belagavi","Mangaluru","Kalaburagi"]
        loan_types=["Personal Loan","Business Loan","Home Loan","Vehicle Loan","Education Loan","Gold Loan"]
        statuses=["Active","Approved","Closed","Overdue","Pending"]

        borrowers=[]
        for i in range(1,61):
            nm=f"{random.choice(first_names)} Customer {i}"
            borrowers.append((nm,f"98{i:08d}",f"customer{i}@loanpro.com",random.choice(cities)+', Karnataka',random.randint(550,850)))

        db.executemany("INSERT INTO borrowers (name, phone, email, address, credit_score) VALUES (?,?,?,?,?)", borrowers)

        def emi(p, r, n):
            rm = r / 12 / 100
            if rm == 0:
                return round(p / n, 2)
            return round(p * rm * (1+rm)**n / ((1+rm)**n - 1), 2)

        for i in range(1,81):
            amount=random.randint(50000,1800000)
            rate=round(random.uniform(7.5,16.5),1)
            tenure=random.choice([12,24,36,48,60,84])
            status=random.choice(statuses)
            paid=0 if status in ["Pending","Approved"] else random.randint(10000,max(15000,amount-5000))
            db.execute("INSERT INTO loans (loan_id, borrower_id, loan_type, amount, interest_rate, tenure_months, emi, status, amount_paid) VALUES (?,?,?,?,?,?,?,?,?)",
                (f"LN-{1000+i}", random.randint(1,60), random.choice(loan_types), amount, rate, tenure, emi(amount,rate,tenure), status, min(paid,amount)))

        for i in range(1,120):
            db.execute("INSERT INTO payments (loan_id, amount, payment_date, note) VALUES (?,?,?,?)",
                (random.randint(1,80), random.randint(5000,45000), (date.today()-timedelta(days=random.randint(1,180))).isoformat(), "Auto generated EMI payment"))

        db.executemany("INSERT INTO audit_logs (action) VALUES (?)", [("Loan approved",),("Bulk EMI processed",),("Risk report generated",)])

    db.commit()
    db.close()
    print("✅ Database initialised.")
