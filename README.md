# LoanPro — Loan Management System

A professional, full-featured loan management system built with Python (Flask) and SQLite.

---

## 🚀 Quick Start

### 1. Install Python (3.9 or higher required)
Download from https://python.org

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Run the application
```bash
python app.py
```

### 4. Open in browser
Visit: http://localhost:5000

---

## 🔐 Login Accounts

| Username | Password   | Role    | Permissions            |
|----------|------------|---------|------------------------|
| admin    | admin123   | Admin   | Full access + delete   |
| officer  | officer123 | Officer | Add/edit loans & borrowers |
| viewer   | viewer123  | Viewer  | View only              |

---

## ✅ Features

- **User Authentication** — Login with role-based access control (Admin / Officer / Viewer)
- **Dashboard** — Key metrics, recent loans, overdue alerts, recovery chart
- **Loan Management** — Add, view, filter, update status, record payments, delete
- **Borrower Management** — Add borrowers with credit scores, view loan history
- **EMI Calculator** — Calculate EMI with amortization schedule and chart
- **Repayment Tracker** — Track active loans, record payments, view payment history
- **Reports & Analytics** — Loan distribution charts, recovery rates, top borrowers

## 🐛 Bugs Fixed from Original

1. **Database connections** — Now properly closed after every request
2. **Overpayment prevention** — Payment amount validated against outstanding balance
3. **Input validation** — All form inputs validated with proper error messages
4. **Hardcoded secret key** — Now reads from environment variable
5. **No login system** — Full authentication system added
6. **No error pages** — Custom 404 and 500 pages added
7. **SQL injection protection** — Parameterised queries throughout
8. **Missing PRAGMA** — WAL mode and foreign keys enforced

## ➕ New Features Added

- Login page with role-based access (Admin / Officer / Viewer)
- Overdue alerts on dashboard
- Loan type filter on Loans page
- Status edit modal (change loan status without deleting)
- Borrower delete (Admin only, only if no loans)
- Recovery rate per loan type in Reports
- Top borrowers table
- Flash messages for all actions (success / error)
- Payment info (outstanding balance) shown in pay modal
- Custom error pages

---

## 📁 Project Structure

```
loanpro/
├── app.py              # Main Flask application (routes, logic)
├── database.py         # Database setup and seed data
├── requirements.txt    # Python dependencies
├── loanpro.db          # SQLite database (auto-created on first run)
└── templates/
    ├── base.html       # Shared layout (sidebar, navigation)
    ├── login.html      # Login page
    ├── dashboard.html  # Dashboard
    ├── loans.html      # Loan records
    ├── borrowers.html  # Borrowers list
    ├── calculator.html # EMI calculator
    ├── repayments.html # Repayment tracker
    ├── reports.html    # Reports & analytics
    └── error.html      # Error page
```

---

## 🔧 Environment Variables (Optional)

For production use, set these environment variables:
```bash
SECRET_KEY=your-very-secure-random-secret-key
```

---

## 📚 Technologies Used

- **Backend**: Python 3, Flask
- **Database**: SQLite (with WAL mode, foreign keys, indexes)
- **Frontend**: HTML5, CSS3, JavaScript
- **Charts**: Chart.js
- **Icons**: Tabler Icons
- **Fonts**: Plus Jakarta Sans, JetBrains Mono (Google Fonts)

---

*Built by Devaraj G. Bilagundi — BCA Project, S.S. Tegnoor Degree College, Gulbarga*
*Upgraded with professional features, bug fixes, and role-based access control*
