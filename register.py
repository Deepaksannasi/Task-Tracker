#!C:/Users/Deepak/AppData/Local/Programs/Python/Python311/python.exe
print("Content-Type: text/html")
print()

import cgi
import cgitb
import os
import re
import hashlib
import pymysql

cgitb.enable()

# Database configuration
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': '',
    'database': 'task',
    'port': 3306
}


def db_connect():
    """Connect to MySQL database"""
    return pymysql.connect(
        host=DB_CONFIG['host'],
        user=DB_CONFIG['user'],
        password=DB_CONFIG['password'],
        database=DB_CONFIG['database'],
        port=DB_CONFIG['port'],
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True
    )


def hash_password(password):
    """Simple password hashing"""
    return hashlib.sha256(password.encode()).hexdigest()


def handle_registration():
    """Handle registration form submission"""
    form = cgi.FieldStorage()

    name = form.getvalue('name', '').strip()
    email = form.getvalue('email', '').strip().lower()
    password = form.getvalue('password', '')
    confirm_password = form.getvalue('confirm_password', '')

    # Validation
    errors = []
    if not name or len(name) < 2:
        errors.append("Name must be at least 2 characters")
    if not email or not re.match(r'^[^@]+@[^@]+\.[^@]+$', email):
        errors.append("Please enter a valid email address")
    if not password or len(password) < 6:
        errors.append("Password must be at least 6 characters")
    if password != confirm_password:
        errors.append("Passwords do not match")

    if errors:
        return "<br>".join(errors)

    conn = None
    cursor = None
    try:
        conn = db_connect()
        cursor = conn.cursor()

        # Check if email exists
        cursor.execute(
            "SELECT id FROM users WHERE email=%s LIMIT 1",
            (email,)
        )
        if cursor.fetchone():
            return "Email already registered"

        # Hash password
        password_hash = hash_password(password)

        # Create user (do NOT generate or store any token)
        cursor.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (%s, %s, %s)",
            (name, email, password_hash)
        )
        conn.commit()
        user_id = cursor.lastrowid

        # Success - redirect to login (no token)
        print(f"""
        <html><head><meta charset="utf-8"></head>
        <body>
          <script>
            alert('Registration successful! Please login with your credentials.');
            window.location.href = 'login.py';
          </script>
          <p>Registration successful. Redirecting to login...</p>
        </body>
        </html>
        """)
        return None

    except Exception as e:
        return f"Server error: {str(e)}"
    finally:
        try:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
        except:
            pass


def render_register_page(error=None):
    """Render the complete registration page (no token behavior)."""
    print("""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Register - Task Tracker</title>
    <!-- Bootstrap CSS -->
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <!-- Font Awesome -->
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        :root {
            --primary-color: #4361ee;
            --secondary-color: #3a0ca3;
        }
        body {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }
        .register-container {
            width: 100%;
            max-width: 500px;
            animation: fadeIn 0.8s ease-out;
        }
        .register-card {
            background: white;
            border-radius: 15px;
            box-shadow: 0 10px 40px rgba(0, 0, 0, 0.2);
            overflow: hidden;
        }
        .register-header {
            background: linear-gradient(to right, var(--primary-color), var(--secondary-color));
            color: white;
            padding: 25px 20px;
            text-align: center;
        }
        .register-header i {
            font-size: 2.5rem;
            margin-bottom: 10px;
        }
        .register-header h1 {
            font-size: 1.6rem;
            font-weight: 600;
            margin: 0;
        }
        .register-body {
            padding: 30px;
        }
        .btn-register {
            background: linear-gradient(to right, var(--primary-color), var(--secondary-color));
            border: none;
            color: white;
            padding: 12px;
            border-radius: 8px;
            font-weight: 600;
            font-size: 1rem;
            width: 100%;
            transition: transform 0.3s, box-shadow 0.3s;
        }
        .btn-register:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(67, 97, 238, 0.4);
        }
        .password-strength {
            height: 5px;
            background: #e9ecef;
            border-radius: 3px;
            margin-top: 5px;
            overflow: hidden;
        }
        .strength-meter {
            height: 100%;
            width: 0%;
            border-radius: 3px;
            transition: width 0.3s, background-color 0.3s;
        }
        .login-link {
            text-align: center;
            margin-top: 20px;
            color: #666;
        }
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(20px); }
            to { opacity: 1; transform: translateY(0); }
        }
    </style>
</head>
<body>
    <div class="register-container">
        <div class="register-card">
            <div class="register-header">
                <i class="fas fa-user-plus"></i>
                <h1>Create Account</h1>
                <p class="mb-0">Join Task Tracker today</p>
            </div>

            <div class="register-body">""")

    if error:
        # keep simple/error text safe
        print(f"""<div class="alert alert-danger alert-dismissible fade show" role="alert">{error}</div>""")

    print("""
                <form method="POST">
                    <div class="row">
                        <div class="col-md-6 mb-3">
                            <label for="name" class="form-label">
                                <i class="fas fa-user me-2"></i>Full Name
                            </label>
                            <input type="text" name="name" class="form-control" placeholder="Enter your full name" required>
                        </div>

                        <div class="col-md-6 mb-3">
                            <label for="email" class="form-label">
                                <i class="fas fa-envelope me-2"></i>Email Address
                            </label>
                            <input type="email" name="email" class="form-control" placeholder="Enter your email" required>
                        </div>
                    </div>

                    <div class="mb-3">
                        <label for="password" class="form-label">
                            <i class="fas fa-lock me-2"></i>Password
                        </label>
                        <input type="password" name="password" id="password" class="form-control" placeholder="Create a password" required minlength="6">

                        <!-- Password Strength Meter -->
                        <div class="password-strength">
                            <div id="strengthMeter" class="strength-meter"></div>
                        </div>
                        <div id="strengthText" class="small text-muted mt-1"></div>

                        <div class="form-text">
                            Password must be at least 6 characters long.
                        </div>
                    </div>

                    <div class="mb-3">
                        <label for="confirm_password" class="form-label">
                            <i class="fas fa-lock me-2"></i>Confirm Password
                        </label>
                        <input type="password" name="confirm_password" class="form-control" placeholder="Confirm your password" required>
                    </div>

                    <div class="d-grid">
                        <button type="submit" class="btn btn-register">
                            <i class="fas fa-user-plus me-2"></i>Create Account
                        </button>
                    </div>
                </form>

                <div class="login-link">
                    <p>Already have an account? <a href="login.py">Login here</a></p>
                </div>
            </div>
        </div>
    </div>

    <!-- Bootstrap JS Bundle -->
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>

    <script>
        // Password strength checker
        document.getElementById('password').addEventListener('input', function() {
            const password = this.value;
            const meter = document.getElementById('strengthMeter');
            const text = document.getElementById('strengthText');

            let strength = 0;
            let textValue = 'Very Weak';

            if (password.length >= 6) strength += 25;
            if (/[a-z]/.test(password)) strength += 25;
            if (/[A-Z]/.test(password)) strength += 25;
            if (/[0-9]/.test(password)) strength += 25;

            meter.style.width = strength + '%';

            if (strength <= 25) {
                meter.style.backgroundColor = '#dc3545';
                textValue = 'Very Weak';
            } else if (strength <= 50) {
                meter.style.backgroundColor = '#ffc107';
                textValue = 'Weak';
            } else if (strength <= 75) {
                meter.style.backgroundColor = '#17a2b8';
                textValue = 'Medium';
            } else {
                meter.style.backgroundColor = '#28a745';
                textValue = 'Strong';
            }

            text.textContent = 'Password Strength: ' + textValue;
        });
    </script>
</body>
</html>
""")


def main():
    """Main function"""
    method = os.environ.get('REQUEST_METHOD', 'GET')

    if method == 'POST':
        error = handle_registration()
        if error:
            render_register_page(error)
    else:
        render_register_page()


if __name__ == '__main__':
    main()
