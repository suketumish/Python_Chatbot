from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
import mysql.connector
import google.generativeai as genai
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # Change this to a secure secret key

# Database configuration
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': '',
    'database': 'aibot'
}

# Configure Gemini API
GEMINI_API_KEY = 'AIzaSyCMUgkLcpaJPXB_C3KJMCXd-Tw5Gy45HIM'
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-pro')

def init_db():
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()
    
    # Create users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(50) UNIQUE NOT NULL,
            email VARCHAR(100) UNIQUE NOT NULL,
            password_hash VARCHAR(256) NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create chats table with user_id
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chats (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            user_message TEXT NOT NULL,
            ai_response TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    conn.commit()
    cursor.close()
    conn.close()

def save_chat(user_id, user_message, ai_response):
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()
    
    query = "INSERT INTO chats (user_id, user_message, ai_response) VALUES (%s, %s, %s)"
    cursor.execute(query, (user_id, user_message, ai_response))
    
    conn.commit()
    cursor.close()
    conn.close()

def get_chat_history(user_id):
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("SELECT * FROM chats WHERE user_id = %s ORDER BY timestamp DESC LIMIT 10", (user_id,))
    history = cursor.fetchall()
    
    cursor.close()
    conn.close()
    return history

@app.route('/')
def home():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    chat_history = get_chat_history(session['user_id'])
    return render_template('index.html', 
        chat_history=chat_history,
        username=session.get('username'),
        email=session.get('email'))    

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        try:
            # Check if username or email already exists
            cursor.execute("SELECT id FROM users WHERE username = %s OR email = %s", (username, email))
            if cursor.fetchone():
                flash('Username or email already exists')
                return redirect(url_for('signup'))
            
            # Create new user
            password_hash = generate_password_hash(password)
            cursor.execute(
                "INSERT INTO users (username, email, password_hash) VALUES (%s, %s, %s)",
                (username, email, password_hash)
            )
            conn.commit()
            
            flash('Successfully registered! Please login.')
            return redirect(url_for('login'))
            
        except Exception as e:
            flash('An error occurred during registration')
            return redirect(url_for('signup'))
        finally:
            cursor.close()
            conn.close()
            
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)
        
        try:
            cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
            user = cursor.fetchone()
            
            if user and check_password_hash(user['password_hash'], password):
                session['user_id'] = user['id']
                session['username'] = user['username']
                session['email'] = user['email']
                session['login_time'] = datetime.now().strftime('%B %d, %Y %I:%M %p')
                flash('Successfully logged in!')
                return redirect(url_for('home'))
            else:
                flash('Invalid username or password')
                return redirect(url_for('login'))
                
        finally:
            cursor.close()
            conn.close()
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out')
    return redirect(url_for('login'))

# @app.route('/')
# def home():
#     if 'user_id' not in session:
#         return redirect(url_for('login'))
    
#     chat_history = get_chat_history(session['user_id'])
#     return render_template('index.html', chat_history=chat_history, username=session.get('username'))

@app.route('/chat', methods=['POST'])
def chat():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
        
    user_message = request.json.get('message', '')
    
    try:
        # Generate response using Gemini
        response = model.generate_content(user_message)
        ai_response = response.text
        
        # Save to database with user_id
        save_chat(session['user_id'], user_message, ai_response)
        
        return jsonify({
            'response': ai_response,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    init_db()
    app.run(debug=True)