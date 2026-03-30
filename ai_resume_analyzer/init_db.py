import sqlite3

conn = sqlite3.connect('database.db')
c = conn.cursor()

# Enable FK enforcement
c.execute('PRAGMA foreign_keys = ON')

# Users table FIRST (parent table must exist before child)
c.execute('''
CREATE TABLE IF NOT EXISTS users (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    email    TEXT,
    password TEXT NOT NULL
)
''')

# Resumes table (child — references users)
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
print("Database initialized successfully.")
