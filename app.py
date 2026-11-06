import os
import sqlite3
from functools import wraps
from flask import (Flask, render_template, request, redirect,
                   url_for, session, flash, g)

app = Flask(__name__)
app.secret_key = "devops-lab-secret"
DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "events.db")


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(e=None):
    db = g.pop("db", None)
    if db:
        db.close()


def init_db():
    db = sqlite3.connect(DB)
    db.executescript("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'student');
    CREATE TABLE IF NOT EXISTS events(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        date TEXT NOT NULL,
        venue TEXT NOT NULL,
        description TEXT);
    CREATE TABLE IF NOT EXISTS registrations(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        event_id INTEGER NOT NULL,
        UNIQUE(user_id, event_id));
    """)
    if db.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
        db.execute("INSERT INTO users(username,password,role) VALUES('admin','admin123','admin')")
        db.execute("INSERT INTO users(username,password,role) VALUES('student1','pass123','student')")
        db.executemany(
            "INSERT INTO events(title,date,venue,description) VALUES(?,?,?,?)",
            [("Hackathon 2026", "2026-12-10", "Main Auditorium", "24-hour coding hackathon"),
             ("Tech Talk: DevOps", "2026-12-15", "Seminar Hall", "Talk on CI/CD with Jenkins and Docker"),
             ("Cultural Fest", "2026-12-20", "Open Ground", "Music, dance and fun")])
    db.commit()
    db.close()


def login_required(f):
    @wraps(f)
    def wrapper(*a, **kw):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*a, **kw)
    return wrapper


def admin_required(f):
    @wraps(f)
    def wrapper(*a, **kw):
        if session.get("role") != "admin":
            flash("Admin access only")
            return redirect(url_for("login"))
        return f(*a, **kw)
    return wrapper


@app.route("/")
def home():
    if "user_id" in session:
        return redirect(url_for("admin" if session["role"] == "admin" else "events"))
    return redirect(url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        u = request.form["username"].strip()
        p = request.form["password"].strip()
        if not u or not p:
            flash("All fields are required")
            return render_template("register.html")
        try:
            db = get_db()
            db.execute("INSERT INTO users(username,password,role) VALUES(?,?,'student')", (u, p))
            db.commit()
            flash("Registration successful. Please login.")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("Username already exists")
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = request.form["username"].strip()
        p = request.form["password"].strip()
        user = get_db().execute(
            "SELECT * FROM users WHERE username=? AND password=?", (u, p)).fetchone()
        if user:
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["role"] = user["role"]
            return redirect(url_for("admin" if user["role"] == "admin" else "events"))
        flash("Invalid username or password")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/events")
@login_required
def events():
    rows = get_db().execute("SELECT * FROM events ORDER BY date").fetchall()
    return render_template("events.html", events=rows)


@app.route("/events/<int:event_id>/register", methods=["POST"])
@login_required
def register_event(event_id):
    db = get_db()
    try:
        db.execute("INSERT INTO registrations(user_id,event_id) VALUES(?,?)",
                   (session["user_id"], event_id))
        db.commit()
    except sqlite3.IntegrityError:
        flash("You are already registered for this event")
    reg = db.execute("SELECT id FROM registrations WHERE user_id=? AND event_id=?",
                     (session["user_id"], event_id)).fetchone()
    return redirect(url_for("confirmation", reg_id=reg["id"]))


@app.route("/confirmation/<int:reg_id>")
@login_required
def confirmation(reg_id):
    reg = get_db().execute("""
        SELECT r.id, e.title, e.date, e.venue, u.username
        FROM registrations r
        JOIN events e ON e.id=r.event_id
        JOIN users u ON u.id=r.user_id
        WHERE r.id=? AND r.user_id=?""", (reg_id, session["user_id"])).fetchone()
    if not reg:
        return redirect(url_for("events"))
    return render_template("confirmation.html", reg=reg)


@app.route("/my-registrations")
@login_required
def my_registrations():
    rows = get_db().execute("""
        SELECT r.id, e.title, e.date, e.venue
        FROM registrations r JOIN events e ON e.id=r.event_id
        WHERE r.user_id=?""", (session["user_id"],)).fetchall()
    return render_template("my_registrations.html", regs=rows)


@app.route("/admin")
@login_required
@admin_required
def admin():
    db = get_db()
    rows = db.execute("""
        SELECT e.*, (SELECT COUNT(*) FROM registrations r WHERE r.event_id=e.id) AS total
        FROM events e ORDER BY e.date""").fetchall()
    stats = {
        "events": db.execute("SELECT COUNT(*) FROM events").fetchone()[0],
        "students": db.execute("SELECT COUNT(*) FROM users WHERE role='student'").fetchone()[0],
        "regs": db.execute("SELECT COUNT(*) FROM registrations").fetchone()[0],
    }
    return render_template("admin.html", events=rows, stats=stats)


@app.route("/admin/add", methods=["POST"])
@login_required
@admin_required
def add_event():
    f = request.form
    get_db().execute("INSERT INTO events(title,date,venue,description) VALUES(?,?,?,?)",
                     (f["title"], f["date"], f["venue"], f["description"]))
    get_db().commit()
    flash("Event added successfully")
    return redirect(url_for("admin"))


@app.route("/admin/delete/<int:event_id>", methods=["POST"])
@login_required
@admin_required
def delete_event(event_id):
    db = get_db()
    db.execute("DELETE FROM registrations WHERE event_id=?", (event_id,))
    db.execute("DELETE FROM events WHERE id=?", (event_id,))
    db.commit()
    flash("Event deleted")
    return redirect(url_for("admin"))


@app.route("/admin/participants/<int:event_id>")
@login_required
@admin_required
def participants(event_id):
    db = get_db()
    event = db.execute("SELECT * FROM events WHERE id=?", (event_id,)).fetchone()
    rows = db.execute("""
        SELECT u.username FROM registrations r
        JOIN users u ON u.id=r.user_id WHERE r.event_id=?""", (event_id,)).fetchall()
    return render_template("participants.html", event=event, people=rows)


init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)