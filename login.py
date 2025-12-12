#!C:/Users/Deepak/AppData/Local/Programs/Python/Python311/python.exe
print("Content-Type: text/html")
print()

import cgi
import cgitb
import os
import hashlib
import secrets
import pymysql
import datetime
import smtplib
from email.message import EmailMessage
import os
import traceback

SMTP_HOST = os.environ.get('SMTP_HOST', 'smtp.gmail.com')
SMTP_PORT = int(os.environ.get('SMTP_PORT', 587))
SMTP_USER = os.environ.get('SMTP_USER', 'deepaknavin321@gmail.com')
SMTP_PASS = os.environ.get('SMTP_PASS', 'yhhu cowl ynrd ihwv')
FROM_EMAIL = os.environ.get('FROM_EMAIL', SMTP_USER or 'no-reply@example.com')

def send_email(to_email, subject, body):



    if not SMTP_HOST or not SMTP_USER or not SMTP_PASS:
        print("<!-- SMTP config missing: SMTP_HOST/SMTP_USER/SMTP_PASS not set -->")
        return False

    try:
        msg = EmailMessage()
        msg['From'] = FROM_EMAIL
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.set_content(body)
        html_body = body.replace('\n', '<br>')
        msg.add_alternative(f"<html><body>{html_body}</body></html>", subtype='html')

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as smtp:
            smtp.ehlo()
            # If port is 587 use STARTTLS
            if SMTP_PORT == 587:
                smtp.starttls()
                smtp.ehlo()
            smtp.login(SMTP_USER, SMTP_PASS)
            smtp.send_message(msg)

        print("<!-- Email sent successfully -->")
        return True

    except Exception as e:
        # Print full traceback in HTML comment for debugging
        tb = traceback.format_exc()
        print("<!-- Email send failed:", str(e), "-->")
        print("<!-- traceback:\n", tb, "-->")
        return False

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


def generate_token():
    """Generate authentication token (used only for password reset links)"""
    return secrets.token_hex(32)


def handle_login():
    """Handle login form submission. Returns error message string or None when redirect already sent."""
    form = cgi.FieldStorage()

    # LOGIN submission
    if form.getvalue("login"):
        email = form.getvalue("Email", '').strip().lower()
        password = form.getvalue("Password", '')

        if not email or not password:
            return "Please enter both email and password"

        conn = None
        cursor = None
        try:
            conn = db_connect()
            cursor = conn.cursor()

            # Get user
            cursor.execute(
                "SELECT id, name, password_hash FROM users WHERE email=%s LIMIT 1",
                (email,)
            )
            user = cursor.fetchone()

            if not user:
                return "Invalid email or password"

            # Verify password
            if hash_password(password) != (user.get('password_hash') or ''):
                return "Invalid email or password"

            # Successful login — DO NOT generate or store a token.
            # Redirect with only user_id in query string (GET)
            redirect_url = f"dashboard.py?user_id={user['id']}"

            # Standard CGI redirect
            print("Status: 302 Found")
            print(f"Location: {redirect_url}")
            print("Content-Type: text/html\n")
            print(f"""
            <html>
              <head><meta charset="utf-8"><title>Redirecting…</title></head>
              <body>
                <script>window.location.href = "{redirect_url}";</script>
                <p>Redirecting to dashboard… If you are not redirected automatically, <a href="{redirect_url}">click here</a>.</p>
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

    # FORGOT PASSWORD submission (keeps reset token behavior)
    elif form.getvalue("forgot"):
        email = form.getvalue("Email", '').strip()
        if not email:
            return "Please enter your registered email"

        conn = None
        cursor = None
        try:
            conn = db_connect()
            cursor = conn.cursor()

            # Check if user exists
            cursor.execute("SELECT id, name FROM users WHERE email=%s LIMIT 1", (email,))
            row = cursor.fetchone()

            if row:
                user_id = row['id']
                user_name = row['name']
                token = generate_token()

                # Store reset token in database (and timestamp)
                cursor.execute(
                    "UPDATE users SET reset_token=%s, token_created=%s WHERE id=%s",
                    (token, datetime.datetime.now(), user_id)
                )
                conn.commit()

                # Create reset link (adjust host/port as needed)
                reset_link = f"http://localhost/task-tracker/reset_password.py?token={token}"
                body = f"""Hello {user_name}!

Click the link below to reset your password:
{reset_link}

This link will expire in 1 hour.

If you didn't request this password reset, please ignore this email.

Best regards,
Task Tracker Team"""

                # Send email (stubbed)
                if send_email(email, "Task Tracker Password Reset", body):
                    print("""
                    <script>
                        alert('Password reset link sent to your email');
                        window.location.href = 'login.py';
                    </script>
                    """)
                    return None
                else:
                    return "Failed to send email. Please try again."
            else:
                return "Email not found in our system"

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

    return None


def render_login_page(error=None):
    """Render the login HTML page (no token generation and no reset password inline form)."""
    print("""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Login - Task Tracker</title>
    <!-- Bootstrap CSS -->
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <!-- Font Awesome -->
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        :root { --primary-color: #4361ee; --secondary-color: #3a0ca3; }
        body { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); height:100vh; display:flex; align-items:center; justify-content:center; font-family: 'Segoe UI', Tahoma, Verdana, sans-serif; margin:0; }
        .login-container { width:100%; max-width:400px; animation: fadeIn 0.8s ease-out; }
        .login-card { background:white; border-radius:15px; box-shadow:0 10px 40px rgba(0,0,0,0.2); overflow:hidden; }
        .login-header { background: linear-gradient(to right, var(--primary-color), var(--secondary-color)); color:white; padding:30px 20px; text-align:center; }
        .form-control { border-radius:8px; padding:12px 15px; border:1px solid #ddd; transition: all 0.3s; }
        .btn-login { background: linear-gradient(to right, var(--primary-color), var(--secondary-color)); border:none; color:white; padding:12px; border-radius:8px; font-weight:600; width:100%; }
        .btn-forgot { background:#ffc107; border:none; color:#212529; padding:12px; border-radius:8px; font-weight:600; width:100%; }
        @keyframes fadeIn { from { opacity:0; transform: translateY(20px); } to { opacity:1; transform: translateY(0); } }
    </style>
</head>
<body>
    <div class="login-container">
        <div class="login-card">
            <div class="login-header">
                <i class="fas fa-tasks"></i>
                <h1>Task Tracker</h1>
                <p class="mb-0">Manage your tasks efficiently</p>
            </div>

            <div class="login-body p-4">""")

    if error:
        # safe-escape isn't implemented here; ensure error strings are simple
        print(f"""<div class="alert alert-danger" role="alert">{error}</div>""")

    # Login form (posts to same script)
    print("""
                <form method="post">
                    <div class="mb-3">
                        <label for="Email" class="form-label"><i class="fas fa-envelope me-2"></i>Email Address</label>
                        <input type="email" name="Email" class="form-control" placeholder="Enter your email" required>
                    </div>

                    <div class="mb-3">
                        <label for="Password" class="form-label"><i class="fas fa-lock me-2"></i>Password</label>
                        <input type="password" name="Password" class="form-control" placeholder="Enter your password" required>
                    </div>

                    <div class="d-grid mb-3">
                        <input type="submit" name="login" class="btn btn-login" value="Login">
                    </div>

                    <div class="text-center mb-3">
                        <a href="#" onclick="document.getElementById('forgotForm').style.display='block'; return false;" class="text-decoration-none">
                            <i class="fas fa-key me-1"></i>Forgot Password?
                        </a>
                    </div>

                    <div class="register-link text-center">
                        <p>Don't have an account? <a href="register.py">Register here</a></p>
                    </div>
                </form>

                <form id="forgotForm" method="post" style="display:none;" class="forgot-form mt-3">
                    <div class="mb-3">
                        <label class="form-label"><i class="fas fa-envelope me-2"></i>Enter your registered Email</label>
                        <input type="email" name="Email" class="form-control" placeholder="Enter your email" required>
                    </div>
                    <div class="d-grid">
                        <input type="submit" name="forgot" class="btn btn-forgot" value="Send Reset Link">
                    </div>
                </form>

            </div>
        </div>
    </div>

    <!-- Bootstrap JS Bundle -->
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
""")


def main():
    """Main function"""
    # Handle form submissions
    error = handle_login()

    # If handle_login returned None and already redirected, stop.
    if error is None:
        # handle_login printed redirect HTML when successful and returned None.
        # But to be safe: if a redirect was printed, exit; otherwise render page.
        # We can't reliably detect if redirect was printed, so if handle_login returned None,
        # assume redirect happened and just exit the script.
        # (If handle_login returned None but did not redirect, we still continue)
        # We'll inspect environment: if login was submitted, we already redirected above.
        form = cgi.FieldStorage()
        if form.getvalue("login"):
            return

    # Show login page (with any error message)
    render_login_page(error)


if __name__ == '__main__':
    main()
