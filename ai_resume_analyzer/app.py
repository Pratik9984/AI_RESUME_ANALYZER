from flask import Flask, render_template, request, session, redirect, url_for, flash
import os
import secrets
from functools import wraps
from resume_parser import extract_text
from analyzer import analyze_resume
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import json
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf', 'docx'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ---------- AUTO-INIT DATABASE ----------
def init_db():
    """Create tables if they don't exist. Safe to call on every startup."""
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('PRAGMA foreign_keys = ON')
    # Users table
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email    TEXT,
            password TEXT NOT NULL
        )
    ''')
    # Resumes table
    c.execute('''
        CREATE TABLE IF NOT EXISTS resumes (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            filename  TEXT,
            content   TEXT,
            score     INTEGER,
            feedback  TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            user_id   INTEGER,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    conn.commit()
    conn.close()

init_db()  

# ---------- CSRF PROTECTION ----------
def generate_csrf_token():
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_hex(32)
    return session['csrf_token']

app.jinja_env.globals['csrf_token'] = generate_csrf_token

def csrf_protect(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if request.method == 'POST':
            token = session.get('csrf_token')
            form_token = request.form.get('csrf_token')
            if not token or token != form_token:
                flash('Invalid request. Please try again.', 'error')
                return redirect(request.referrer or url_for('login'))
        return f(*args, **kwargs)
    return decorated

# ---------- HELPERS ----------
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_db():
    conn = sqlite3.connect('database.db')
    conn.execute('PRAGMA foreign_keys = ON')
    return conn

# ---------- ROUTES ----------
@app.route('/')
def landing():
    if 'user_id' in session:
        return redirect(url_for('profile'))
    return redirect(url_for('login'))

@app.route('/index')
def index():
    if 'user_id' not in session:
        flash("Please login first.", 'error')
        return redirect(url_for('login'))
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
@csrf_protect
def upload():
    if 'user_id' not in session:
        flash("Please login to upload resumes.", 'error')
        return redirect(url_for('login'))

    file = request.files.get('resume')
    if not file or file.filename == '':
        flash("No file selected.", 'error')
        return redirect(url_for('index'))

    if not allowed_file(file.filename):
        flash("Only PDF and DOCX files are allowed.", 'error')
        return redirect(url_for('index'))

    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)

    try:
        resume_text = extract_text(filepath)
        
        # Passing None for API key so it uses the fallback in analyzer.py
        result = analyze_resume(resume_text, api_key=None)
        score, feedback_dict = result if isinstance(result, tuple) else (0, {})

        try:
            score = max(0, min(100, int(float(score))))
        except (ValueError, TypeError):
            score = 0

        score_deg = round((score / 100) * 360, 2)

        conn = get_db()
        try:
            c = conn.cursor()
            c.execute(
                'INSERT INTO resumes (filename, content, score, feedback, user_id) VALUES (?, ?, ?, ?, ?)',
                (filename, resume_text, score, json.dumps(feedback_dict or {}), session['user_id'])
            )
            conn.commit()
        finally:
            conn.close()

    finally:
        if os.path.exists(filepath):
            os.remove(filepath)

    return render_template('result.html', score=score, score_deg=score_deg, feedback=feedback_dict)

@app.route('/profile')
def profile():
    if 'user_id' not in session:
        flash("Please login to view profile.", 'error')
        return redirect(url_for('login'))

    username = session.get('username')
    conn = get_db()
    try:
        c = conn.cursor()
        c.execute(
            'SELECT filename, score, feedback, timestamp FROM resumes WHERE user_id = ? ORDER BY timestamp DESC',
            (session['user_id'],)
        )
        rows = c.fetchall()
    finally:
        conn.close()

    resumes = []
    for filename, score, feedback_json, timestamp in rows:
        try:
            feedback = json.loads(feedback_json) if feedback_json else {}
        except json.JSONDecodeError:
            feedback = {}
        try:
            ts = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
            formatted_ts = ts.strftime('%b %d, %Y at %I:%M %p')
        except Exception:
            formatted_ts = timestamp
        resumes.append({
            "filename": filename,
            "score": score,
            "feedback": feedback,
            "timestamp": formatted_ts
        })

    return render_template('profile.html', username=username, resumes=resumes)

@app.route('/register', methods=['GET', 'POST'])
@csrf_protect
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        confirm = request.form.get('confirm_password', '')

        if not username or not password:
            flash('Username and password are required.', 'error')
            return render_template('register.html')

        if password != confirm:
            flash('Passwords do not match.', 'error')
            return render_template('register.html')

        if len(password) < 8:
            flash('Password must be at least 8 characters.', 'error')
            return render_template('register.html')

        conn = get_db()
        try:
            c = conn.cursor()
            c.execute(
                'INSERT INTO users (username, email, password) VALUES (?, ?, ?)',
                (username, email, generate_password_hash(password))
            )
            conn.commit()
            flash('Account created! Please log in.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('That username is already taken.', 'error')
        finally:
            conn.close()

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
@csrf_protect
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        conn = get_db()
        try:
            c = conn.cursor()
            c.execute('SELECT id, password FROM users WHERE username = ?', (username,))
            user = c.fetchone()
        finally:
            conn.close()

        if user and check_password_hash(user[1], password):
            session['user_id'] = user[0]
            session['username'] = username
            return redirect(url_for('profile'))

        flash('Invalid username or password.', 'error')

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
