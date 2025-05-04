from flask import Flask, render_template, jsonify, request, redirect, url_for, send_from_directory, session, abort, flash
from flask_cors import CORS
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
import os
import secrets
from functools import wraps
from urllib.parse import quote

app = Flask(__name__)
CORS(app)
app.secret_key = secrets.token_hex(32)  # Stronger secret key
app.config['SESSION_COOKIE_SECURE'] = True  # Requires HTTPS in production
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# Constants
DATABASE = "museum.db"
PAYMENT_AMOUNT = 5.00  # USD

# --- Database Utilities ---
def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row  # Return rows as dictionaries
    return conn

def init_db():
    with get_db_connection() as conn:
        # Artifacts table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS artifacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT NOT NULL,
                image_path TEXT NOT NULL,
                model_path TEXT NOT NULL,
                price REAL DEFAULT 5.00
            )
        """)
        
        # Users table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Payments table (for tracking transactions)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                artifact_id INTEGER NOT NULL,
                amount REAL NOT NULL,
                payment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                transaction_id TEXT,
                status TEXT DEFAULT 'pending',
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (artifact_id) REFERENCES artifacts(id)
            )
        """)
        
        # Insert default artifacts if they don't exist
        artifacts = [
        ("Ancient Stone Sword", 
         "A historical artifact used in battles during the medieval period.", 
         "static/models/artifact2.jpg", 
         "static/models/Ancient-stone-sword-obj.obj"),
        
        ("Megalodon Teeth", 
         "The fossilized teeth of the prehistoric Megalodon shark.", 
         "static/models/tooth.jpg", 
         "static/models/megalodon teeth.obj"),
        
        ("Ancient Book", 
         "A preserved book from ancient times with historical significance.", 
         "static/models/book.jpg", 
         "static/models/An_ancient_book_aged.obj"),
        
        ("T-Rex Skull", 
         "A fossilized skull of the mighty Tyrannosaurus Rex.", 
         "static/models/skull.jpg", 
         "static/models/skull1.obj"),
        
        ("Beetle Totem", 
         "Totem of Undying.", 
         "static/models/beetle.jpg", 
         "static/models/beetle.obj"),
    ]
        
        for artifact in artifacts:
            if not conn.execute("SELECT 1 FROM artifacts WHERE name = ?", (artifact[0],)).fetchone():
                conn.execute(
                    "INSERT INTO artifacts (name, description, image_path, model_path) VALUES (?, ?, ?, ?)",
                    artifact
                )
        conn.commit()

# --- Authentication Decorator ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            flash('Please log in to access this page', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# --- Routes ---
@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        
        if not username or not password:
            flash('Username and password are required', 'error')
            return redirect(url_for('login'))
        
        with get_db_connection() as conn:
            user = conn.execute(
                "SELECT id, username, password FROM users WHERE username = ?", 
                (username,)
            ).fetchone()
            
            if user and check_password_hash(user['password'], password):
                session['user_id'] = user['id']
                session['username'] = user['username']
                session['paid_models'] = []  # Initialize empty list for paid models
                flash('Login successful!', 'success')
                return redirect(url_for('museum'))
        
        flash('Invalid username or password', 'error')
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        
        if not username or not password:
            flash('Username and password are required', 'error')
            return redirect(url_for('signup'))
        
        if len(password) < 8:
            flash('Password must be at least 8 characters', 'error')
            return redirect(url_for('signup'))
        
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        
        try:
            with get_db_connection() as conn:
                conn.execute(
                    "INSERT INTO users (username, password) VALUES (?, ?)",
                    (username, hashed_password)
                )
                conn.commit()
            flash('Account created successfully! Please login', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Username already exists', 'error')
    
    return render_template('signup.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out', 'info')
    return redirect(url_for('login'))

@app.route('/museum')
def museum():
    with get_db_connection() as conn:
        artifacts = conn.execute("SELECT * FROM artifacts").fetchall()
    return render_template("museum.html", artifacts=artifacts)  # Corrected this line

@app.route('/api/artifacts')
@login_required
def get_artifacts():
    with get_db_connection() as conn:
        artifacts = conn.execute(
            "SELECT name, description, image_path, model_path FROM artifacts"
        ).fetchall()
    return jsonify([dict(artifact) for artifact in artifacts])

@app.route('/viewer')
@login_required
def viewer():
    model = request.args.get('model')
    name = request.args.get('name')
    
    if not model or not name:
        abort(400, description="Missing model or name parameters")
    
    # Check if model is in session's paid_models
    if model in session.get('paid_models', []):
        return render_template('viewer.html', model=model, name=name)
    
    # Check database payment records
    with get_db_connection() as conn:
        artifact = conn.execute(
            "SELECT id FROM artifacts WHERE model_path = ?", 
            (model,)
        ).fetchone()
        
        if artifact:
            payment = conn.execute(
                """SELECT 1 FROM payments 
                WHERE user_id = ? AND artifact_id = ? AND status = 'completed'""",
                (session['user_id'], artifact['id'])
            ).fetchone()
            
            if payment:
                if 'paid_models' not in session:
                    session['paid_models'] = []
                session['paid_models'].append(model)
                return render_template('viewer.html', model=model, name=name)
    
    # If not paid, redirect to payment
    return redirect(url_for('payment', model=model, name=name))

@app.route('/payment')
@login_required
def payment():
    model = request.args.get('model')
    name = request.args.get('name')
    
    if not model or not name:
        abort(400, description="Missing model or name parameters")
    
    return render_template('payment.html', 
                         model=model, 
                         name=name,
                         amount=PAYMENT_AMOUNT)
@app.route('/check_payment', methods=['POST'])
@login_required
def check_payment():
    data = request.get_json()
    model_path = data.get('modelPath')
    
    # Check if user has access (in session or database)
    has_access = model_path in session.get('paid_models', [])
    
    if not has_access:
        # Check database
        with get_db_connection() as conn:
            artifact = conn.execute("SELECT id FROM artifacts WHERE model_path = ?", (model_path,)).fetchone()
            if artifact:
                payment = conn.execute(
                    "SELECT 1 FROM payments WHERE user_id = ? AND artifact_id = ? AND status = 'completed'",
                    (session['user_id'], artifact['id'])
                ).fetchone()
                has_access = bool(payment)
    
    return jsonify({'has_access': has_access})

@app.route('/verify_payment', methods=['POST'])
@login_required
def verify_payment():
    data = request.get_json()
    model = data.get('model')
    name = data.get('name')
    
    if not model or not name:
        return jsonify({'success': False, 'error': 'Missing parameters'}), 400
    
    # Record payment in database
    with get_db_connection() as conn:
        artifact = conn.execute("SELECT id FROM artifacts WHERE model_path = ?", (model,)).fetchone()
        if artifact:
            conn.execute(
                """INSERT INTO payments 
                (user_id, artifact_id, amount, status) 
                VALUES (?, ?, ?, ?)""",
                (session['user_id'], artifact['id'], PAYMENT_AMOUNT, 'completed')
            )
            conn.commit()
    
    # Update session
    if 'paid_models' not in session:
        session['paid_models'] = []
    session['paid_models'].append(model)
    
    return jsonify({
        'success': True,
        'redirect_url': f'/viewer?model={quote(model)}&name={quote(name)}'
    })

@app.route('/assets/<path:filename>')
def assets(filename):
    return send_from_directory('assets', filename)

# Error Handlers
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(403)
def forbidden(e):
    return render_template('403.html'), 403

@app.errorhandler(500)
def server_error(e):
    return render_template('500.html'), 500

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)
