import os
import math
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
from database import init_db, get_db
from datetime import datetime, date, timedelta
from functools import wraps

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-in-production-use-env-var")

# ─── AUTH HELPERS ────────────────────────────────────────────────────────────

USERS = {
    "admin": {"password": "admin123", "role": "Admin", "name": "Administrator"},
    "officer": {"password": "officer123", "role": "Officer", "name": "Loan Officer"},
    "borrower": {"password": "borrower123", "role": "Borrower", "name": "Demo Borrower", "borrower_id": 1},
}

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("login"))
        if session.get("role") not in ("Admin",):
            flash("You need Admin access for this action.", "error")
            return redirect(url_for("dashboard"))
        return f(*args, **kwargs)
    return decorated

def can_write():
    return session.get("role") in ("Admin", "Officer")

# ─── FINANCE HELPERS ─────────────────────────────────────────────────────────

def calc_emi(principal, annual_rate, months):
    if months == 0:
        return 0
    if annual_rate == 0:
        return round(principal / months, 2)
    r = annual_rate / 12 / 100
    emi = principal * r * (1 + r)**months / ((1 + r)**months - 1)
    return round(emi, 2)

def amortization_schedule(principal, annual_rate, months):
    r = annual_rate / 12 / 100
    emi = calc_emi(principal, annual_rate, months)
    schedule = []
    balance = principal
    for i in range(1, months + 1):
        interest = round(balance * r, 2)
        principal_part = round(emi - interest, 2)
        balance = round(max(0, balance - principal_part), 2)
        schedule.append({
            "month": i,
            "emi": emi,
            "principal": principal_part,
            "interest": interest,
            "balance": balance,
        })
    return schedule

# ─── AUTH ROUTES ─────────────────────────────────────────────────────────────

@app.route("/login", methods=["GET", "POST"])
def login():
    if "user" in session:
        return redirect(url_for("dashboard"))
    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")
        user = USERS.get(username)
        if user and user["password"] == password:
            session["user"] = username
            session["role"] = user["role"]
            session["name"] = user["name"]
            if "borrower_id" in user:
                session["borrower_id"] = user["borrower_id"]
            return redirect(url_for("dashboard"))
        error = "Invalid username or password."
    return render_template("login.html", error=error)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# ─── MAIN PAGES ──────────────────────────────────────────────────────────────

@app.route("/")
@login_required
def dashboard():
    db = get_db()
    try:
        is_borrower = session.get("role") == "Borrower"
        borrower_id = session.get("borrower_id")

        if is_borrower:
            stats = {
                "total_loans":     db.execute("SELECT COUNT(*) FROM loans WHERE borrower_id=?", (borrower_id,)).fetchone()[0],
                "total_disbursed": db.execute("SELECT COALESCE(SUM(amount),0) FROM loans WHERE status IN ('Active','Closed','Overdue') AND borrower_id=?", (borrower_id,)).fetchone()[0],
                "total_recovered": db.execute("SELECT COALESCE(SUM(amount_paid),0) FROM loans WHERE borrower_id=?", (borrower_id,)).fetchone()[0],
                "overdue_count":   db.execute("SELECT COUNT(*) FROM loans WHERE status='Overdue' AND borrower_id=?", (borrower_id,)).fetchone()[0],
                "active_count":    db.execute("SELECT COUNT(*) FROM loans WHERE status='Active' AND borrower_id=?", (borrower_id,)).fetchone()[0],
                "pending_count":   db.execute("SELECT COUNT(*) FROM loans WHERE status='Pending' AND borrower_id=?", (borrower_id,)).fetchone()[0],
                "total_borrowers": 1,
            }
            recent = db.execute(
                "SELECT l.*, b.name AS borrower_name FROM loans l JOIN borrowers b ON l.borrower_id=b.id WHERE l.borrower_id=? ORDER BY l.created_at DESC LIMIT 8",
                (borrower_id,)
            ).fetchall()
            overdue_loans = db.execute(
                "SELECT l.*, b.name AS borrower_name, b.phone FROM loans l JOIN borrowers b ON l.borrower_id=b.id WHERE l.status='Overdue' AND l.borrower_id=? ORDER BY l.created_at ASC LIMIT 5",
                (borrower_id,)
            ).fetchall()
        else:
            stats = {
                "total_loans":     db.execute("SELECT COUNT(*) FROM loans").fetchone()[0],
                "total_disbursed": db.execute("SELECT COALESCE(SUM(amount),0) FROM loans WHERE status IN ('Active','Closed','Overdue')").fetchone()[0],
                "total_recovered": db.execute("SELECT COALESCE(SUM(amount_paid),0) FROM loans").fetchone()[0],
                "overdue_count":   db.execute("SELECT COUNT(*) FROM loans WHERE status='Overdue'").fetchone()[0],
                "active_count":    db.execute("SELECT COUNT(*) FROM loans WHERE status='Active'").fetchone()[0],
                "pending_count":   db.execute("SELECT COUNT(*) FROM loans WHERE status='Pending'").fetchone()[0],
                "total_borrowers": db.execute("SELECT COUNT(*) FROM borrowers").fetchone()[0],
            }
            recent = db.execute(
                "SELECT l.*, b.name AS borrower_name FROM loans l JOIN borrowers b ON l.borrower_id=b.id ORDER BY l.created_at DESC LIMIT 8"
            ).fetchall()
            overdue_loans = db.execute(
                "SELECT l.*, b.name AS borrower_name, b.phone FROM loans l JOIN borrowers b ON l.borrower_id=b.id WHERE l.status='Overdue' ORDER BY l.created_at ASC LIMIT 5"
            ).fetchall()

        portfolio_health = round((stats["total_recovered"] / max(stats["total_disbursed"],1))*100,2)
        stats["portfolio_health"] = portfolio_health
    finally:
        db.close()
    return render_template("dashboard.html", stats=stats, recent=recent, overdue_loans=overdue_loans)

@app.route("/loans")
@login_required
def loans():
    db = get_db()
    try:
        is_borrower = session.get("role") == "Borrower"
        borrower_id = session.get("borrower_id")
        
        q      = request.args.get("q", "")
        status = request.args.get("status", "")
        ltype  = request.args.get("type", "")
        sql    = "SELECT l.*, b.name AS borrower_name FROM loans l JOIN borrowers b ON l.borrower_id=b.id WHERE 1=1"
        params = []
        
        if is_borrower:
            sql += " AND l.borrower_id=?"
            params.append(borrower_id)
            
        if q:
            sql += " AND (b.name LIKE ? OR l.loan_id LIKE ?)"
            params += [f"%{q}%", f"%{q}%"]
        if status:
            sql += " AND l.status=?"
            params.append(status)
        if ltype:
            sql += " AND l.loan_type=?"
            params.append(ltype)
        sql += " ORDER BY l.created_at DESC"
        loans_list = db.execute(sql, params).fetchall()
        
        if is_borrower:
            borrowers = db.execute("SELECT id, name FROM borrowers WHERE id=?", (borrower_id,)).fetchall()
        else:
            borrowers  = db.execute("SELECT id, name FROM borrowers ORDER BY name").fetchall()
    finally:
        db.close()
    return render_template("loans.html", loans=loans_list, borrowers=borrowers,
                           q=q, status=status, ltype=ltype, can_write=can_write())

@app.route("/loans/add", methods=["POST"])
@login_required
def add_loan():
    if not can_write():
        flash("Insufficient permissions.", "error")
        return redirect(url_for("loans"))
    db = get_db()
    try:
        data = request.form
        # Input validation
        try:
            amount       = float(data["amount"])
            interest_rate= float(data["interest_rate"])
            tenure_months= int(data["tenure_months"])
        except (ValueError, KeyError) as e:
            flash(f"Invalid input: {e}", "error")
            return redirect(url_for("loans"))
        if amount <= 0 or interest_rate < 0 or tenure_months <= 0:
            flash("Amount, rate, and tenure must be positive.", "error")
            return redirect(url_for("loans"))

        emi = calc_emi(amount, interest_rate, tenure_months)
        loan_count = db.execute("SELECT COUNT(*) FROM loans").fetchone()[0]
        loan_id    = f"LN-{loan_count + 1001:04d}"
        db.execute(
            "INSERT INTO loans (loan_id, borrower_id, loan_type, amount, interest_rate, tenure_months, emi, status, amount_paid) VALUES (?,?,?,?,?,?,?,?,0)",
            (loan_id, data["borrower_id"], data["loan_type"], amount, interest_rate, tenure_months, emi, data.get("status","Pending"))
        )
        db.commit()
        flash(f"Loan {loan_id} added successfully.", "success")
    except Exception as e:
        flash(f"Error adding loan: {e}", "error")
    finally:
        db.close()
    return redirect(url_for("loans"))

@app.route("/loans/<int:loan_id>/edit", methods=["POST"])
@login_required
def edit_loan(loan_id):
    if not can_write():
        flash("Insufficient permissions.", "error")
        return redirect(url_for("loans"))
    db = get_db()
    try:
        new_status = request.form.get("status")
        if new_status:
            db.execute("UPDATE loans SET status=? WHERE id=?", (new_status, loan_id))
            db.commit()
            flash("Loan status updated.", "success")
    finally:
        db.close()
    return redirect(url_for("loans"))

@app.route("/loans/delete/<int:loan_id>", methods=["POST"])
@admin_required
def delete_loan(loan_id):
    db = get_db()
    try:
        loan = db.execute("SELECT loan_id FROM loans WHERE id=?", (loan_id,)).fetchone()
        db.execute("DELETE FROM payments WHERE loan_id=?", (loan_id,))
        db.execute("DELETE FROM loans WHERE id=?", (loan_id,))
        db.commit()
        flash(f"Loan {loan['loan_id'] if loan else ''} deleted.", "success")
    finally:
        db.close()
    return redirect(url_for("loans"))

@app.route("/loans/<int:loan_id>/pay", methods=["POST"])
@login_required
def record_payment(loan_id):
    if not can_write():
        flash("Insufficient permissions.", "error")
        return redirect(url_for("repayments"))
    db = get_db()
    try:
        try:
            amount = float(request.form["amount"])
        except (ValueError, KeyError):
            flash("Invalid payment amount.", "error")
            return redirect(url_for("repayments"))

        loan = db.execute("SELECT * FROM loans WHERE id=?", (loan_id,)).fetchone()
        if not loan:
            flash("Loan not found.", "error")
            return redirect(url_for("repayments"))

        # Prevent overpayment
        remaining = loan["amount"] - loan["amount_paid"]
        if amount <= 0:
            flash("Payment amount must be positive.", "error")
            return redirect(url_for("repayments"))
        if amount > remaining + 0.01:
            flash(f"Payment ₹{amount:,.0f} exceeds outstanding balance ₹{remaining:,.0f}.", "error")
            return redirect(url_for("repayments"))

        amount = min(amount, remaining)
        db.execute("UPDATE loans SET amount_paid = amount_paid + ? WHERE id=?", (amount, loan_id))
        new_paid = loan["amount_paid"] + amount
        if new_paid >= loan["amount"] - 0.01:
            db.execute("UPDATE loans SET status='Closed' WHERE id=?", (loan_id,))
        db.execute(
            "INSERT INTO payments (loan_id, amount, payment_date, note) VALUES (?,?,?,?)",
            (loan_id, amount, date.today().isoformat(), request.form.get("note", ""))
        )
        db.commit()
        flash(f"Payment of ₹{amount:,.0f} recorded successfully.", "success")
    finally:
        db.close()
    return redirect(url_for("repayments"))

@app.route("/borrowers")
@login_required
def borrowers():
    db = get_db()
    try:
        is_borrower = session.get("role") == "Borrower"
        borrower_id = session.get("borrower_id")

        q = request.args.get("q", "")
        sql = """SELECT b.*, COUNT(l.id) as loan_count,
                        COALESCE(SUM(l.amount),0) as total_borrowed,
                        COALESCE(SUM(l.amount - l.amount_paid),0) as outstanding
                 FROM borrowers b LEFT JOIN loans l ON b.id=l.borrower_id WHERE 1=1"""
        params = []
        
        if is_borrower:
            sql += " AND b.id=?"
            params.append(borrower_id)
            
        if q:
            sql += " AND (b.name LIKE ? OR b.phone LIKE ? OR b.email LIKE ?)"
            params += [f"%{q}%", f"%{q}%", f"%{q}%"]
        sql += " GROUP BY b.id ORDER BY b.name"
        borrowers_list = db.execute(sql, params).fetchall()
    finally:
        db.close()
    return render_template("borrowers.html", borrowers=borrowers_list, q=q, can_write=can_write())

@app.route("/borrowers/add", methods=["POST"])
@login_required
def add_borrower():
    if not can_write():
        flash("Insufficient permissions.", "error")
        return redirect(url_for("borrowers"))
    db = get_db()
    try:
        d = request.form
        name = d.get("name","").strip()
        if not name:
            flash("Borrower name is required.", "error")
            return redirect(url_for("borrowers"))
        try:
            credit_score = int(d.get("credit_score", 700))
            credit_score = max(300, min(900, credit_score))
        except ValueError:
            credit_score = 700
        db.execute(
            "INSERT INTO borrowers (name, phone, email, address, credit_score) VALUES (?,?,?,?,?)",
            (name, d.get("phone",""), d.get("email",""), d.get("address",""), credit_score)
        )
        db.commit()
        flash(f"Borrower '{name}' added successfully.", "success")
    finally:
        db.close()
    return redirect(url_for("borrowers"))

@app.route("/borrowers/delete/<int:borrower_id>", methods=["POST"])
@admin_required
def delete_borrower(borrower_id):
    db = get_db()
    try:
        has_loans = db.execute("SELECT COUNT(*) FROM loans WHERE borrower_id=?", (borrower_id,)).fetchone()[0]
        if has_loans > 0:
            flash("Cannot delete borrower with existing loans.", "error")
            return redirect(url_for("borrowers"))
        db.execute("DELETE FROM borrowers WHERE id=?", (borrower_id,))
        db.commit()
        flash("Borrower deleted.", "success")
    finally:
        db.close()
    return redirect(url_for("borrowers"))

@app.route("/calculator")
@login_required
def calculator():
    try:
        principal = float(request.args.get("principal", 200000))
        rate      = float(request.args.get("rate", 10.5))
        months    = int(request.args.get("months", 24))
        principal = max(1, principal)
        rate      = max(0, rate)
        months    = max(1, min(360, months))
    except (ValueError, TypeError):
        principal, rate, months = 200000, 10.5, 24

    emi      = calc_emi(principal, rate, months)
    total    = round(emi * months, 2)
    interest = round(total - principal, 2)
    schedule = amortization_schedule(principal, rate, months)
    return render_template("calculator.html", principal=principal, rate=rate,
                           months=months, emi=emi, total=total,
                           interest=interest, schedule=schedule)

@app.route("/repayments")
@login_required
def repayments():
    db = get_db()
    try:
        is_borrower = session.get("role") == "Borrower"
        borrower_id = session.get("borrower_id")

        if is_borrower:
            upcoming = db.execute(
                "SELECT l.*, b.name AS borrower_name FROM loans l JOIN borrowers b ON l.borrower_id=b.id WHERE l.status IN ('Active','Overdue','Approved') AND l.borrower_id=? ORDER BY l.status DESC, b.name",
                (borrower_id,)
            ).fetchall()
            history = db.execute(
                "SELECT p.*, l.loan_id, b.name AS borrower_name FROM payments p JOIN loans l ON p.loan_id=l.id JOIN borrowers b ON l.borrower_id=b.id WHERE l.borrower_id=? ORDER BY p.payment_date DESC, p.id DESC LIMIT 30",
                (borrower_id,)
            ).fetchall()
        else:
            upcoming = db.execute(
                "SELECT l.*, b.name AS borrower_name FROM loans l JOIN borrowers b ON l.borrower_id=b.id WHERE l.status IN ('Active','Overdue','Approved') ORDER BY l.status DESC, b.name"
            ).fetchall()
            history = db.execute(
                "SELECT p.*, l.loan_id, b.name AS borrower_name FROM payments p JOIN loans l ON p.loan_id=l.id JOIN borrowers b ON l.borrower_id=b.id ORDER BY p.payment_date DESC, p.id DESC LIMIT 30"
            ).fetchall()
    finally:
        db.close()
    return render_template("repayments.html", upcoming=upcoming, history=history, can_write=can_write())

@app.route("/reports")
@login_required
def reports():
    db = get_db()
    try:
        is_borrower = session.get("role") == "Borrower"
        borrower_id = session.get("borrower_id")

        if is_borrower:
            by_type   = [dict(r) for r in db.execute("SELECT loan_type, COUNT(*) as cnt, COALESCE(SUM(amount),0) as total, COALESCE(SUM(amount_paid),0) as recovered FROM loans WHERE borrower_id=? GROUP BY loan_type ORDER BY total DESC", (borrower_id,)).fetchall()]
            by_status = [dict(r) for r in db.execute("SELECT status, COUNT(*) as cnt FROM loans WHERE borrower_id=? GROUP BY status ORDER BY cnt DESC", (borrower_id,)).fetchall()]
            monthly   = db.execute(
                "SELECT strftime('%Y-%m', created_at) as month, COALESCE(SUM(amount),0) as disbursed, COALESCE(SUM(amount_paid),0) as collected FROM loans WHERE borrower_id=? GROUP BY month ORDER BY month DESC LIMIT 12",
                (borrower_id,)
            ).fetchall()
            total_loans     = db.execute("SELECT COUNT(*) FROM loans WHERE borrower_id=?", (borrower_id,)).fetchone()[0]
            total_disbursed = db.execute("SELECT COALESCE(SUM(amount),0) FROM loans WHERE borrower_id=?", (borrower_id,)).fetchone()[0]
            total_recovered = db.execute("SELECT COALESCE(SUM(amount_paid),0) FROM loans WHERE borrower_id=?", (borrower_id,)).fetchone()[0]
            overdue_amount  = db.execute("SELECT COALESCE(SUM(amount-amount_paid),0) FROM loans WHERE status='Overdue' AND borrower_id=?", (borrower_id,)).fetchone()[0]
            top_borrowers   = db.execute(
                "SELECT b.name, COUNT(l.id) as loans, COALESCE(SUM(l.amount),0) as total FROM borrowers b JOIN loans l ON b.id=l.borrower_id WHERE b.id=? GROUP BY b.id",
                (borrower_id,)
            ).fetchall()
        else:
            by_type   = [dict(r) for r in db.execute("SELECT loan_type, COUNT(*) as cnt, COALESCE(SUM(amount),0) as total, COALESCE(SUM(amount_paid),0) as recovered FROM loans GROUP BY loan_type ORDER BY total DESC").fetchall()]
            by_status = [dict(r) for r in db.execute("SELECT status, COUNT(*) as cnt FROM loans GROUP BY status ORDER BY cnt DESC").fetchall()]
            monthly   = db.execute(
                "SELECT strftime('%Y-%m', created_at) as month, COALESCE(SUM(amount),0) as disbursed, COALESCE(SUM(amount_paid),0) as collected FROM loans GROUP BY month ORDER BY month DESC LIMIT 12"
            ).fetchall()
            total_loans     = db.execute("SELECT COUNT(*) FROM loans").fetchone()[0]
            total_disbursed = db.execute("SELECT COALESCE(SUM(amount),0) FROM loans").fetchone()[0]
            total_recovered = db.execute("SELECT COALESCE(SUM(amount_paid),0) FROM loans").fetchone()[0]
            overdue_amount  = db.execute("SELECT COALESCE(SUM(amount-amount_paid),0) FROM loans WHERE status='Overdue'").fetchone()[0]
            top_borrowers   = db.execute(
                "SELECT b.name, COUNT(l.id) as loans, COALESCE(SUM(l.amount),0) as total FROM borrowers b JOIN loans l ON b.id=l.borrower_id GROUP BY b.id ORDER BY total DESC LIMIT 5"
            ).fetchall()
    finally:
        db.close()
    return render_template("reports.html", by_type=by_type, by_status=by_status,
                           monthly=monthly, total_loans=total_loans,
                           total_disbursed=total_disbursed, total_recovered=total_recovered,
                           overdue_amount=overdue_amount, top_borrowers=top_borrowers)


@app.route("/analytics")
@login_required
def analytics():
    db=get_db()
    try:
        is_borrower = session.get("role") == "Borrower"
        borrower_id = session.get("borrower_id")

        if is_borrower:
            high_value=db.execute("SELECT l.loan_id,b.name,l.amount,l.status FROM loans l JOIN borrowers b ON l.borrower_id=b.id WHERE l.borrower_id=? ORDER BY l.amount DESC LIMIT 10", (borrower_id,)).fetchall()
            risky=db.execute("SELECT name,credit_score FROM borrowers WHERE credit_score < 650 AND id=? ORDER BY credit_score ASC LIMIT 10", (borrower_id,)).fetchall()
            branch_stats=[] # Don't show branch stats to borrowers
        else:
            high_value=db.execute("SELECT l.loan_id,b.name,l.amount,l.status FROM loans l JOIN borrowers b ON l.borrower_id=b.id ORDER BY l.amount DESC LIMIT 10").fetchall()
            risky=db.execute("SELECT name,credit_score FROM borrowers WHERE credit_score < 650 ORDER BY credit_score ASC LIMIT 10").fetchall()
            branch_stats=db.execute("SELECT * FROM branches").fetchall()
    finally:
        db.close()
    return render_template("analytics.html",high_value=high_value,risky=risky,branch_stats=branch_stats)

@app.route("/collections")
@login_required
def collections():
    db=get_db()
    try:
        is_borrower = session.get("role") == "Borrower"
        borrower_id = session.get("borrower_id")

        if is_borrower:
            overdue=db.execute("SELECT l.loan_id,b.name,l.amount,l.amount_paid,l.status FROM loans l JOIN borrowers b ON l.borrower_id=b.id WHERE l.status='Overdue' AND l.borrower_id=? ORDER BY l.amount DESC", (borrower_id,)).fetchall()
        else:
            overdue=db.execute("SELECT l.loan_id,b.name,l.amount,l.amount_paid,l.status FROM loans l JOIN borrowers b ON l.borrower_id=b.id WHERE l.status='Overdue' ORDER BY l.amount DESC").fetchall()
    finally:
        db.close()
    return render_template("collections.html", overdue=overdue)

# ─── API ENDPOINTS ───────────────────────────────────────────────────────────

@app.route("/api/emi")
@login_required
def api_emi():
    try:
        p = float(request.args.get("principal", 0))
        r = float(request.args.get("rate", 0))
        n = int(request.args.get("months", 0))
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid parameters"}), 400
    emi = calc_emi(p, r, n)
    return jsonify({"emi": emi, "total": round(emi * n, 2), "interest": round(emi * n - p, 2)})

@app.route("/api/schedule")
@login_required
def api_schedule():
    try:
        p = float(request.args.get("principal", 0))
        r = float(request.args.get("rate", 0))
        n = int(request.args.get("months", 0))
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid parameters"}), 400
    return jsonify(amortization_schedule(p, r, n))

@app.route("/api/dashboard_stats")
@login_required
def api_dashboard_stats():
    db = get_db()
    try:
        by_type   = [dict(row) for row in db.execute("SELECT loan_type, COUNT(*) as cnt, COALESCE(SUM(amount),0) as total FROM loans GROUP BY loan_type").fetchall()]
        by_status = [dict(row) for row in db.execute("SELECT status, COUNT(*) as cnt FROM loans GROUP BY status").fetchall()]
        monthly   = [dict(row) for row in db.execute(
            "SELECT strftime('%Y-%m', created_at) as month, COALESCE(SUM(amount),0) as disbursed FROM loans GROUP BY month ORDER BY month DESC LIMIT 6"
        ).fetchall()]
    finally:
        db.close()
    return jsonify({"by_type": by_type, "by_status": by_status, "monthly": monthly})

# ─── ERROR HANDLERS ──────────────────────────────────────────────────────────

@app.errorhandler(404)
def not_found(e):
    return render_template("error.html", code=404, message="Page not found"), 404

@app.errorhandler(500)
def server_error(e):
    return render_template("error.html", code=500, message="Internal server error"), 500

# ─── TEMPLATE CONTEXT ────────────────────────────────────────────────────────

@app.context_processor
def inject_globals():
    return {
        "current_user": session.get("name", ""),
        "current_role": session.get("role", ""),
        "current_username": session.get("user", ""),
        "today": date.today().isoformat(),
    }

if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5000)
