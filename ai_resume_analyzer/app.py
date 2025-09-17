from flask import Flask, render_template, request, session, redirect, url_for, flash
import os
from resume_parser import extract_text
from analyzer import analyze_resume
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
import json

app = Flask(__name__)
app.secret_key = "supersecretkey"  # 🔑 required for session & flash

UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Ensure upload folder exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# ---------- LANDING PAGE ----------
@app.route('/')
def landing():
    if 'user_id' in session:
        return redirect(url_for('profile'))  # Redirect to profile instead of index
    return redirect(url_for('login'))


# ---------- INDEX / UPLOAD PAGE ----------
@app.route('/index')
def index():
    if 'user_id' not in session:
        flash("Please login first.")
        return redirect(url_for('login'))
    return render_template('index.html')


@app.route('/upload', methods=['POST'])
def upload():
    if 'user_id' not in session:
        flash("Please login to upload resumes.")
        return redirect(url_for('login'))

    file = request.files.get('resume')
    if not file:
        flash("No file selected.")
        return redirect(url_for('index'))

    filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
    file.save(filepath)

    # Extract text & analyze
    resume_text = extract_text(filepath)
    score, feedback_dict = analyze_resume(resume_text)

    # Ensure score is numeric and between 0-100
    try:
        score = float(score)
        score = max(0, min(100, int(score)))
    except Exception:
        score = 0

    # Precompute degree for conic-gradient
    score_deg = (score / 100) * 360

    # Save to database
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('''
        INSERT INTO resumes (filename, content, score, feedback, user_id) 
        VALUES (?, ?, ?, ?, ?)
    ''', (file.filename, resume_text, score, json.dumps(feedback_dict or {}), session['user_id']))
    conn.commit()
    conn.close()

    return render_template('result.html', score=score, score_deg=score_deg, feedback=feedback_dict)


# ---------- PROFILE PAGE ----------
@app.route('/profile')
def profile():
    if 'user_id' not in session:
        flash("Please login to view profile.")
        return redirect(url_for('login'))

    username = session.get('username')

    # Fetch resume history for this user
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('''
        SELECT filename, score, feedback, timestamp 
        FROM resumes 
        WHERE user_id = ? 
        ORDER BY timestamp DESC
    ''', (session['user_id'],))
    rows = c.fetchall()
    conn.close()

    # Safely parse JSON feedback
    resumes = []
    for row in rows:
        filename, score, feedback_json, timestamp = row
        try:
            feedback = json.loads(feedback_json) if feedback_json else {}
        except json.JSONDecodeError:
            feedback = {}  # fallback if JSON is empty or invalid
        resumes.append({
            "filename": filename,
            "score": score,
            "feedback": feedback,
            "timestamp": timestamp
        })

    return render_template('profile.html', username=username, resumes=resumes)


# ---------- REGISTER ----------
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = generate_password_hash(request.form['password'])

        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        try:
            c.execute('INSERT INTO users (username, password) VALUES (?, ?)', (username, password))
            conn.commit()
            flash('Registration successful. Please log in.')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Username already exists.')
        conn.close()
    return render_template('register.html')


# ---------- LOGIN ----------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute('SELECT id, password FROM users WHERE username = ?', (username,))
        user = c.fetchone()
        conn.close()

        if user and check_password_hash(user[1], password):
            session['user_id'] = user[0]
            session['username'] = username
            return redirect(url_for('profile'))
        else:
            flash('Invalid credentials.')
    return render_template('login.html')


# ---------- LOGOUT ----------
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


# ---------- RUN APP ----------
if __name__ == '__main__':
    app.run(debug=True)
