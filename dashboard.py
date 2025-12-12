#!C:/Users/Deepak/AppData/Local/Programs/Python/Python311/python.exe

import cgi
import cgitb
import os
import json
import pymysql
from urllib.parse import parse_qs
import datetime
import smtplib
import tempfile
import traceback
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import sys
import io

# safe debug log path
DEBUG_LOG = os.path.join(tempfile.gettempdir(), "dashboard_debug.log")

def log_debug(msg: str) -> None:
    try:
        ts = datetime.datetime.now().isoformat(sep=' ')
        with open(DEBUG_LOG, "a", encoding="utf-8") as f:
            f.write(f"{ts} | {msg}\n")
    except Exception:
        try:
            print(f"{ts} | {msg}", file=sys.stderr)
        except:
            pass

# ensure stdout uses UTF-8 (helps with CGI output)
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

cgitb.enable()

# Database configuration (update to your settings)
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': '',
    'database': 'task',
    'port': 3306
}

# Email config placeholders
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
EMAIL_FROM = "deepaknavin321@gmail.com"
EMAIL_PASSWORD = "deepaknavin321_password_replace_me"

def send_email_notification(to_email, subject, body):
    try:
        msg = MIMEMultipart()
        msg['Subject'] = subject
        msg['From'] = EMAIL_FROM
        msg['To'] = to_email
        msg.attach(MIMEText(body, 'plain'))
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_FROM, EMAIL_PASSWORD)
        server.sendmail(EMAIL_FROM, [to_email], msg.as_string())
        server.quit()
        return True
    except Exception as e:
        log_debug("Email error: " + str(e))
        return False

def db_connect():
    return pymysql.connect(
        host=DB_CONFIG['host'],
        user=DB_CONFIG['user'],
        password=DB_CONFIG['password'],
        database=DB_CONFIG['database'],
        port=DB_CONFIG['port'],
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True
    )

# ----------------- Authentication helpers -----------------
def get_user_id_from_request():
    user_id = ''
    qs = os.environ.get('QUERY_STRING', '') or ''
    params = parse_qs(qs)
    user_id = params.get('user_id', [''])[0] or ''
    if not user_id:
        try:
            form = cgi.FieldStorage()
            user_id = form.getvalue('user_id', '') or ''
        except Exception:
            user_id = ''
    return user_id

def authenticate_user_by_id():
    user_id = get_user_id_from_request()
    if not user_id:
        return None, "No user ID provided. Please login."

    try:
        uid = int(user_id)
    except ValueError:
        return None, "Invalid user ID."

    try:
        conn = db_connect()
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, email FROM users WHERE id=%s LIMIT 1", (uid,))
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        if not row:
            return None, "User not found."
        return {'id': row['id'], 'name': row.get('name') or '', 'email': row.get('email')}, None
    except Exception as e:
        try:
            cursor.close(); conn.close()
        except:
            pass
        return None, f"Database error: {str(e)}"

def resolve_user_from_request(parsed_post_data=None):
    # Priority: parsed_post_data.user_id -> token -> Authorization header -> query-string user_id
    if parsed_post_data and parsed_post_data.get('user_id'):
        try:
            uid = int(parsed_post_data.get('user_id'))
        except Exception:
            return None, "Invalid user_id"
        try:
            conn = db_connect()
            cur = conn.cursor()
            cur.execute("SELECT id,name,email FROM users WHERE id=%s LIMIT 1", (uid,))
            row = cur.fetchone()
            cur.close(); conn.close()
            if not row:
                return None, "User not found"
            return {'id': row['id'], 'name': row['name'], 'email': row['email']}, None
        except Exception as e:
            return None, f"Database error: {e}"

    token = None
    if parsed_post_data:
        token = parsed_post_data.get('token') or parsed_post_data.get('api_token')
    if not token:
        auth = os.environ.get('HTTP_AUTHORIZATION', '') or ''
        if auth.lower().startswith('bearer '):
            token = auth.split(None, 1)[1].strip()
    if token:
        try:
            conn = db_connect()
            cur = conn.cursor()
            cur.execute("SELECT id,name,email,token_created FROM users WHERE api_token=%s LIMIT 1", (token,))
            row = cur.fetchone()
            cur.close(); conn.close()
            if not row:
                return None, "Invalid token"
            return {'id': row['id'], 'name': row['name'], 'email': row['email']}, None
        except Exception as e:
            return None, f"Database error: {e}"

    # fallback: try GET query string user_id
    qs = os.environ.get('QUERY_STRING', '') or ''
    params = parse_qs(qs)
    q_user_id = params.get('user_id', [''])[0]
    if q_user_id:
        try:
            uid = int(q_user_id)
            conn = db_connect()
            cur = conn.cursor()
            cur.execute("SELECT id,name,email FROM users WHERE id=%s LIMIT 1", (uid,))
            row = cur.fetchone()
            cur.close(); conn.close()
            if not row:
                return None, "User not found"
            return {'id': row['id'], 'name': row['name'], 'email': row['email']}, None
        except Exception as e:
            return None, f"Database error: {e}"

    return None, "No user ID provided. Please login."

# ----------------- Stats & reminders -----------------
def check_due_date_reminders():
    try:
        conn = db_connect()
        cursor = conn.cursor()
        reminder_date = datetime.datetime.now() + datetime.timedelta(days=2)
        reminder_date_str = reminder_date.strftime('%Y-%m-%d')
        cursor.execute("""
            SELECT t.*, u.email, u.name 
            FROM tasks t 
            JOIN users u ON t.user_id = u.id 
            WHERE t.due_date = %s 
              AND t.reminder_sent = FALSE 
              AND t.status != 'Completed'
        """, (reminder_date_str,))
        rows = cursor.fetchall() or []
        for task in rows:
            subject = f"Task Tracker: Reminder - '{task['title']}' Due Soon"
            body = f"""Hello {task['name']},

This is a reminder that your task '{task['title']}' is due in 2 days.

Task Details:
• Title: {task['title']}
• Due Date: {task['due_date']}
• Status: {task['status']}
• Description: {task['description'] or 'No description'}

Please complete the task before the due date.

Best regards,
Task Tracker System"""
            if send_email_notification(task['email'], subject, body):
                cursor.execute("UPDATE tasks SET reminder_sent = TRUE WHERE id = %s", (task['id'],))
                conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        log_debug("Reminder check error: " + str(e))

def get_user_stats(user_id):
    default_stats = {
        'total': 0, 'pending': 0, 'in-progress': 0, 'completed': 0,
        'due_today': 0, 'overdue': 0, 'upcoming': 0
    }
    try:
        if user_id is None or user_id == '':
            return {'stats': default_stats.copy(), 'recent_tasks': []}
        uid = int(user_id)
        conn = db_connect()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as total FROM tasks WHERE user_id=%s", (uid,))
        row = cursor.fetchone() or {}
        total = int(row.get('total') or 0)

        cursor.execute("""
            SELECT status, COUNT(*) as count
            FROM tasks
            WHERE user_id=%s
            GROUP BY status
        """, (uid,))
        rows = cursor.fetchall() or []
        status_counts = {r['status']: r['count'] for r in rows}

        stats = {
            'total': total,
            'pending': int(status_counts.get('Pending', 0) or 0),
            'in-progress': int(status_counts.get('In-Progress', 0) or 0),
            'completed': int(status_counts.get('Completed', 0) or 0),
            'due_today': 0,
            'overdue': 0,
            'upcoming': 0
        }

        today = datetime.datetime.now().date()
        today_str = today.strftime('%Y-%m-%d')
        upcoming_str = (today + datetime.timedelta(days=7)).strftime('%Y-%m-%d')

        cursor.execute("SELECT COUNT(*) as due_today FROM tasks WHERE user_id=%s AND due_date = %s AND status != 'Completed'", (uid, today_str))
        row = cursor.fetchone() or {}
        stats['due_today'] = int(row.get('due_today') or 0)

        cursor.execute("SELECT COUNT(*) as overdue FROM tasks WHERE user_id=%s AND due_date < %s AND status != 'Completed'", (uid, today_str))
        row = cursor.fetchone() or {}
        stats['overdue'] = int(row.get('overdue') or 0)

        cursor.execute("SELECT COUNT(*) as upcoming FROM tasks WHERE user_id=%s AND due_date BETWEEN %s AND %s AND status != 'Completed'", (uid, today_str, upcoming_str))
        row = cursor.fetchone() or {}
        stats['upcoming'] = int(row.get('upcoming') or 0)

        cursor.execute("""
            SELECT
                id,
                title,
                COALESCE(description, '') AS description,
                status,
                COALESCE(priority, 'medium') AS priority,
                DATE_FORMAT(created_at, '%%Y-%%m-%%d %%H:%%i:%%s') AS created_at,
                DATE_FORMAT(due_date, '%%Y-%%m-%%d') AS due_date,
                reminder_sent
            FROM tasks
            WHERE user_id=%s
            ORDER BY
                CASE
                    WHEN due_date IS NULL THEN 3
                    WHEN due_date < CURDATE() AND status NOT IN ('Completed', 'Done') THEN 0
                    WHEN due_date = CURDATE() AND status NOT IN ('Completed', 'Done') THEN 1
                    WHEN due_date > CURDATE() AND status NOT IN ('Completed', 'Done') THEN 2
                    ELSE 3
                END,
                due_date ASC,
                CASE
                    WHEN COALESCE(priority, 'medium') = 'urgent' THEN 0
                    WHEN COALESCE(priority, 'medium') = 'high' THEN 1
                    WHEN COALESCE(priority, 'medium') = 'medium' THEN 2
                    WHEN COALESCE(priority, 'medium') = 'low' THEN 3
                    ELSE 4
                END,
                created_at DESC
            LIMIT 5
        """, (uid,))
        recent_tasks = cursor.fetchall() or []

        cursor.close()
        conn.close()
        return {'stats': stats, 'recent_tasks': recent_tasks}
    except Exception as e:
        log_debug("get_user_stats error: " + str(e) + "\n" + traceback.format_exc())
        return {'stats': default_stats.copy(), 'recent_tasks': []}

# ----------------- API router and endpoints -----------------
def json_response(data):
    print("Content-Type: application/json\n")
    print(json.dumps(data, default=str))

def create_task_api(user, data):
    try:
        if 'title' not in data or not data['title']:
            return json_response({'success': False, 'error': 'Task title is required'})

        conn = db_connect()
        cursor = conn.cursor()

        task_data = {
            'user_id': user['id'],
            'title': data['title'][:255],
            'description': data.get('description'),
            'status': data.get('status', 'Pending'),
            'priority': data.get('priority', 'medium'),
            'due_date': data.get('due_date'),
            'reminder_sent': False
        }

        columns = ', '.join(task_data.keys())
        placeholders = ', '.join(['%s'] * len(task_data))
        sql = f"INSERT INTO tasks ({columns}) VALUES ({placeholders})"
        cursor.execute(sql, list(task_data.values()))
        task_id = cursor.lastrowid
        conn.commit()

        cursor.close()
        conn.close()

        return json_response({'success': True, 'message': 'Task created successfully', 'task_id': task_id})
    except Exception as e:
        log_debug("create_task_api error: " + str(e))
        return json_response({'success': False, 'error': str(e)})

def update_task_api(user, data):
    try:
        task_id = data.get('id') or data.get('task_id')
        if not task_id:
            return json_response({'success': False, 'error': 'Task ID is required'})
        try:
            task_id = int(task_id)
        except:
            return json_response({'success': False, 'error': 'Invalid Task ID'})

        allowed_fields = ['title', 'description', 'status', 'priority', 'due_date', 'reminder_sent']
        updates = []
        params = []
        for field in allowed_fields:
            if field in data:
                val = data[field]
                if field == "title":
                    val = val[:255]
                updates.append(f"{field}=%s")
                params.append(val)
        if not updates:
            return json_response({'success': False, 'error': 'No fields to update'})

        params.append(task_id)
        params.append(user['id'])

        conn = db_connect()
        cur = conn.cursor()
        cur.execute("SELECT id FROM tasks WHERE id=%s AND user_id=%s", (task_id, user['id']))
        if not cur.fetchone():
            cur.close(); conn.close()
            return json_response({'success': False, 'error': 'Task not found'})

        sql = f"UPDATE tasks SET {', '.join(updates)}, updated_at=NOW() WHERE id=%s AND user_id=%s"
        cur.execute(sql, params)
        conn.commit()
        cur.close()
        conn.close()
        return json_response({'success': True, 'message': 'Task updated successfully'})
    except Exception as e:
        log_debug("update_task_api error: " + str(e))
        return json_response({'success': False, 'error': str(e)})

def delete_task_api(user, task_id):
    try:
        if not task_id:
            return json_response({'success': False, 'error': 'Task ID is required'})
        try:
            tid = int(task_id)
        except Exception:
            return json_response({'success': False, 'error': 'Invalid Task ID'})

        conn = db_connect()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM tasks WHERE id=%s AND user_id=%s", (tid, user['id']))
        task = cursor.fetchone()
        if not task:
            cursor.close(); conn.close()
            return json_response({'success': False, 'error': 'Task not found or unauthorized'})

        cursor.execute("DELETE FROM tasks WHERE id=%s AND user_id=%s", (tid, user['id']))
        conn.commit()
        cursor.close()
        conn.close()
        return json_response({'success': True, 'message': 'Task deleted successfully', 'deleted_id': tid})
    except Exception as e:
        log_debug("delete_task_api error: " + str(e))
        return json_response({'success': False, 'error': str(e)})

def list_tasks_api(user):
    try:
        conn = db_connect()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, title, description, status, COALESCE(priority, 'medium') as priority,
                   DATE_FORMAT(created_at, '%%Y-%%m-%%d %%H:%%i:%%s') as created_at,
                   DATE_FORMAT(due_date, '%%Y-%%m-%%d') as due_date, reminder_sent
            FROM tasks
            WHERE user_id=%s
            ORDER BY created_at DESC
        """, (user['id'],))
        tasks = cursor.fetchall()
        cursor.close()
        conn.close()
        return json_response({'success': True, 'data': {'tasks': tasks}})
    except Exception as e:
        log_debug("list_tasks_api error: " + str(e))
        return json_response({'success': False, 'error': str(e)})

def handle_api_request():
    try:
        query_string = os.environ.get('QUERY_STRING', '') or ''
        params = parse_qs(query_string)
        action = params.get('action', [''])[0]

        content_type = (os.environ.get('CONTENT_TYPE') or '').lower()
        content_length = int(os.environ.get('CONTENT_LENGTH') or 0)

        post_data = {}

        if 'application/json' in content_type:
            if content_length > 0:
                raw = sys.stdin.read(content_length)
                try:
                    post_data = json.loads(raw)
                except Exception as e:
                    log_debug("JSON parse error: " + str(e))
                    post_data = {}
        else:
            try:
                form = cgi.FieldStorage()
                for key in form.keys():
                    post_data[key] = form.getvalue(key)
            except Exception as e:
                log_debug("FieldStorage error: " + str(e))
                post_data = {}

        if post_data.get("action"):
            action = post_data.get("action")
        if isinstance(action, list):
            action = action[0] if action else ''
        action = str(action).strip().lower()

        log_debug("API DEBUG: " + json.dumps({
            "query_params": {k: params[k] for k in params},
            "post_keys": list(post_data.keys()),
            "action_final": action,
            "content_type": content_type
        }, default=str))

        user, error = resolve_user_from_request(parsed_post_data=post_data)
        if error:
            return json_response({'success': False, 'error': error})

        if action == "create":
            return create_task_api(user, post_data)
        elif action == "delete":
            task_id = post_data.get("id") or params.get("id", [''])[0]
            return delete_task_api(user, task_id)
        elif action == "update":
            return update_task_api(user, post_data)
        elif action == "list":
            return list_tasks_api(user)
        else:
            return json_response({'success': False, 'error': 'Invalid action', 'hint': 'Use action=create | delete | list | update'})
    except Exception as e:
        log_debug("handle_api_request Exception: " + str(e) + "\n" + traceback.format_exc())
        return json_response({'success': False, 'error': str(e)})

# ----------------- Render dashboard -----------------
def render_dashboard(user, stats_data):
    if stats_data:
        stats = stats_data['stats']
        recent_tasks = stats_data['recent_tasks']
        recent_tasks_json = json.dumps(recent_tasks, default=str)
    else:
        stats = {'total': 0, 'pending': 0, 'in-progress': 0, 'completed': 0, 'due_today': 0, 'overdue': 0}
        recent_tasks_json = '[]'

    # Try to send reminders (best-effort)
    check_due_date_reminders()
    print(f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Dashboard - Task Tracker Pro</title>
            <!-- Bootstrap CSS -->
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
            <!-- Font Awesome -->
            <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
            <!-- Flatpickr for date picker -->
            <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/flatpickr/dist/flatpickr.min.css">
            <style>
                :root {{
                    --primary-color: #4361ee;
                    --primary-light: #eef2ff;
                    --secondary-color: #3a0ca3;
                    --success-color: #28a745;
                    --warning-color: #ffc107;
                    --info-color: #17a2b8;
                    --danger-color: #dc3545;
                    --overdue-color: #e74c3c;
                    --due-today-color: #f39c12;
                    --upcoming-color: #2ecc71;
                    --light-color: #f8f9fa;
                    --dark-color: #2c3e50;
                    --border-color: #e0e6ed;
                    --shadow-color: rgba(67, 97, 238, 0.15);
                    --card-bg: #ffffff;
                    --body-bg: #f8fafc;
                    --glass-bg: rgba(255, 255, 255, 0.9);
                }}

                * {{
                    margin: 0;
                    padding: 0;
                    box-sizing: border-box;
                }}

                body {{
                    font-family: 'Segoe UI', 'Poppins', Tahoma, Geneva, Verdana, sans-serif;
                    background: linear-gradient(135deg, #f8fafc 0%, #eef2ff 100%);
                    color: var(--dark-color);
                    line-height: 1.6;
                    min-height: 100vh;
                    overflow-x: hidden;
                }}

                /* Modern Glassmorphism Navbar */
                .navbar {{
                    background: linear-gradient(135deg, rgba(67, 97, 238, 0.95), rgba(58, 12, 163, 0.95));
                    backdrop-filter: blur(10px);
                    -webkit-backdrop-filter: blur(10px);
                    box-shadow: 0 8px 32px rgba(31, 38, 135, 0.2);
                    padding: 1rem 0;
                    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
                }}

                .navbar-brand {{
                    font-weight: 700;
                    font-size: 1.8rem;
                    color: white !important;
                    background: linear-gradient(45deg, #fff, #ffd700);
                    -webkit-background-clip: text;
                    -webkit-text-fill-color: transparent;
                    background-clip: text;
                    text-shadow: 0 2px 4px rgba(0,0,0,0.1);
                }}

                .navbar-brand i {{
                    color: #ffd700;
                    margin-right: 10px;
                    filter: drop-shadow(0 2px 3px rgba(0,0,0,0.2));
                }}

                /* Enhanced Stats Cards with Glassmorphism */
                .stats-card {{
                    background: var(--glass-bg);
                    backdrop-filter: blur(10px);
                    -webkit-backdrop-filter: blur(10px);
                    border-radius: 20px;
                    padding: 25px;
                    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.08);
                    margin-bottom: 25px;
                    border: 1px solid rgba(255, 255, 255, 0.3);
                    transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
                    position: relative;
                    overflow: hidden;
                    min-height: 180px;
                }}

                .stats-card::before {{
                    content: '';
                    position: absolute;
                    top: 0;
                    left: 0;
                    right: 0;
                    height: 5px;
                    background: linear-gradient(90deg, var(--primary-color), var(--secondary-color));
                    border-radius: 20px 20px 0 0;
                }}

                .stats-card:hover {{
                    transform: translateY(-10px) scale(1.02);
                    box-shadow: 0 20px 40px rgba(67, 97, 238, 0.2);
                }}

                .stats-icon {{
                    width: 70px;
                    height: 70px;
                    border-radius: 15px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    font-size: 2rem;
                    margin-bottom: 20px;
                    background: linear-gradient(135deg, var(--primary-light), white);
                    box-shadow: 0 8px 20px rgba(0,0,0,0.1);
                    transition: all 0.3s ease;
                }}

                .stats-card:hover .stats-icon {{
                    transform: rotate(15deg) scale(1.1);
                }}

                .stats-number {{
                    font-size: 3rem;
                    font-weight: 800;
                    margin: 10px 0;
                    background: linear-gradient(45deg, var(--primary-color), var(--secondary-color));
                    -webkit-background-clip: text;
                    -webkit-text-fill-color: transparent;
                    background-clip: text;
                    text-shadow: 0 2px 10px rgba(67, 97, 238, 0.2);
                    font-family: 'Poppins', sans-serif;
                }}

                .stats-label {{
                    color: #6c757d;
                    font-weight: 600;
                    font-size: 0.9rem;
                    text-transform: uppercase;
                    letter-spacing: 1px;
                }}

                /* Progress bars for stats */
                .stats-progress {{
                    height: 6px;
                    background: rgba(0,0,0,0.05);
                    border-radius: 3px;
                    margin-top: 15px;
                    overflow: hidden;
                }}

                .stats-progress-bar {{
                    height: 100%;
                    border-radius: 3px;
                    transition: width 1s ease-in-out;
                }}

                /* Modern Card Styling */
                .card {{
                    border: none;
                    border-radius: 20px;
                    overflow: hidden;
                    box-shadow: 0 10px 30px rgba(0,0,0,0.08);
                    margin-bottom: 25px;
                    transition: all 0.3s ease;
                    background: var(--glass-bg);
                    backdrop-filter: blur(10px);
                    -webkit-backdrop-filter: blur(10px);
                }}

                .card:hover {{
                    box-shadow: 0 15px 40px rgba(0,0,0,0.12);
                    transform: translateY(-5px);
                }}

                .card-header {{
                    background: linear-gradient(to right, var(--primary-light), rgba(255,255,255,0.9));
                    border-bottom: 1px solid var(--border-color);
                    padding: 1.5rem;
                    font-weight: 600;
                    color: var(--primary-color);
                    font-size: 1.2rem;
                    display: flex;
                    align-items: center;
                    gap: 10px;
                }}

                /* Enhanced Task Cards */
                .task-card {{
                    background: white;
                    border: 1px solid var(--border-color);
                    border-radius: 15px;
                    padding: 20px;
                    margin-bottom: 15px;
                    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
                    position: relative;
                    overflow: hidden;
                    box-shadow: 0 5px 15px rgba(0,0,0,0.05);
                }}

                .task-card::before {{
                    content: '';
                    position: absolute;
                    left: 0;
                    top: 0;
                    bottom: 0;
                    width: 6px;
                    border-radius: 15px 0 0 15px;
                }}

                .task-card.pending::before {{ 
                    background: linear-gradient(to bottom, var(--warning-color), #ff9800);
                }}
                .task-card.in-progress::before {{ 
                    background: linear-gradient(to bottom, var(--info-color), #0dcaf0);
                }}
                .task-card.completed::before {{ 
                    background: linear-gradient(to bottom, var(--success-color), #20c997);
                }}

                /* Due date status indicators */
                .task-card.overdue {{
                    border-left: 6px solid var(--overdue-color);
                    background: linear-gradient(to right, rgba(231, 76, 60, 0.05), white);
                    animation: pulse 2s infinite;
                }}

                .task-card.due-today {{
                    border-left: 6px solid var(--due-today-color);
                    background: linear-gradient(to right, rgba(243, 156, 18, 0.05), white);
                }}

                .task-card.upcoming {{
                    border-left: 6px solid var(--upcoming-color);
                    background: linear-gradient(to right, rgba(46, 204, 113, 0.05), white);
                }}

                .task-card.no-due {{
                    border-left: 6px solid #95a5a6;
                }}

                @keyframes pulse {{
                    0% {{ box-shadow: 0 5px 15px rgba(231, 76, 60, 0.1); }}
                    50% {{ box-shadow: 0 5px 25px rgba(231, 76, 60, 0.2); }}
                    100% {{ box-shadow: 0 5px 15px rgba(231, 76, 60, 0.1); }}
                }}

                .task-card:hover {{
                    transform: translateY(-5px);
                    box-shadow: 0 10px 25px rgba(0,0,0,0.1);
                }}

                /* Task action buttons */
                .task-actions {{
                    display: flex;
                    gap: 8px;
                    margin-top: 10px;
                }}

                .action-btn {{
                    width: 35px;
                    height: 35px;
                    border-radius: 50%;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    transition: all 0.3s ease;
                    border: none;
                    font-size: 0.9rem;
                }}

                .action-btn:hover {{
                    transform: scale(1.1) rotate(5deg);
                }}

                .btn-edit {{
                    background: linear-gradient(135deg, var(--warning-color), #ff9800);
                    color: white;
                }}

                .btn-delete {{
                    background: linear-gradient(135deg, var(--danger-color), #c82333);
                    color: white;
                }}

                /* Modal Enhancement */
                .modal-content {{
                    border-radius: 25px;
                    overflow: hidden;
                    border: none;
                    box-shadow: 0 30px 60px rgba(0,0,0,0.3);
                    background: var(--glass-bg);
                    backdrop-filter: blur(20px);
                    -webkit-backdrop-filter: blur(20px);
                }}

                .modal-header {{
                    background: linear-gradient(to right, var(--primary-color), var(--secondary-color));
                    color: white;
                    border-bottom: none;
                    padding: 1.5rem 2rem;
                }}

                .modal-title {{
                    font-weight: 700;
                    font-size: 1.4rem;
                }}

                .modal-body {{
                    padding: 2rem;
                }}

                .modal-footer {{
                    border-top: 1px solid var(--border-color);
                    padding: 1.5rem 2rem;
                }}

                .form-control, .form-select {{
                    border-radius: 12px;
                    padding: 0.875rem 1rem;
                    border: 2px solid var(--border-color);
                    transition: all 0.3s ease;
                    font-size: 0.95rem;
                }}

                .form-control:focus, .form-select:focus {{
                    border-color: var(--primary-color);
                    box-shadow: 0 0 0 0.3rem rgba(67, 97, 238, 0.2);
                    transform: translateY(-2px);
                }}

                /* Empty State Enhancement */
                .empty-state {{
                    text-align: center;
                    padding: 80px 30px;
                    background: linear-gradient(135deg, rgba(255,255,255,0.9), rgba(248,249,250,0.9));
                    border-radius: 20px;
                    backdrop-filter: blur(10px);
                    -webkit-backdrop-filter: blur(10px);
                }}

                .empty-state i {{
                    font-size: 5rem;
                    background: linear-gradient(45deg, var(--primary-color), var(--secondary-color));
                    -webkit-background-clip: text;
                    -webkit-text-fill-color: transparent;
                    margin-bottom: 25px;
                    opacity: 0.8;
                    filter: drop-shadow(0 5px 10px rgba(67, 97, 238, 0.2));
                }}

                /* User Info Card */
                .user-info-card {{
                    background: linear-gradient(145deg, white, var(--primary-light));
                    border-left: 5px solid var(--primary-color);
                    border-radius: 20px;
                    padding: 25px;
                }}

                .user-info-card p {{
                    padding: 12px 0;
                    border-bottom: 1px solid var(--border-color);
                    display: flex;
                    align-items: center;
                    gap: 15px;
                    margin: 0;
                    font-size: 0.95rem;
                }}

                .user-info-card p:last-child {{
                    border-bottom: none;
                }}

                .user-info-card i {{
                    width: 25px;
                    color: var(--primary-color);
                    font-size: 1.2rem;
                }}

                /* Notification Toast */
                .notification-toast {{
                    position: fixed;
                    top: 20px;
                    right: 20px;
                    z-index: 9999;
                    min-width: 300px;
                }}

                .loading-overlay {{
                    display: none;
                    position: fixed;
                    top: 0;
                    left: 0;
                    width: 100%;
                    height: 100%;
                    background: rgba(0,0,0,0.5);
                    z-index: 9998;
                    justify-content: center;
                    align-items: center;
                }}

                .loading-spinner {{
                    color: white;
                    font-size: 3rem;
                }}

                /* Animations */
                @keyframes fadeInUp {{
                    from {{ 
                        opacity: 0; 
                        transform: translateY(30px) scale(0.95); 
                    }}
                    to {{ 
                        opacity: 1; 
                        transform: translateY(0) scale(1); 
                    }}
                }}

                .animate-in {{
                    animation: fadeInUp 0.8s cubic-bezier(0.175, 0.885, 0.32, 1.275) forwards;
                }}
            </style>
        </head>
        <body>
            <!-- Loading Overlay -->
            <div class="loading-overlay" id="loadingOverlay">
                <div class="loading-spinner">
                    <i class="fas fa-spinner fa-spin"></i>
                </div>
            </div>

            <!-- Notification Toast Container -->
            <div class="notification-toast" id="notificationToast"></div>

            <!-- Navigation -->
            <nav class="navbar navbar-expand-lg navbar-dark">
                <div class="container">
                    <a class="navbar-brand" href="#">
                        <i class="fas fa-tasks me-2"></i>Task Tracker
                    </a>
                    <div class="navbar-text text-white d-flex align-items-center">
                        <div class="me-3 text-end">
                            
                            <strong class="d-block" style="font-size: 1rem;">{user['name']}</strong>
                        </div>
                     
               
                <button class="btn btn-sm btn-outline-light" onclick="logout()">
                    <i class="fas fa-sign-out-alt me-1"></i>Logout
                </button>
            </div>
                    </div>
                </div>
            </nav>

            <div class="container mt-4 animate-in">
                <!-- Stats Overview -->
                <div class="row mb-4">
                    <div class="col-md-3">
                        <div class="stats-card">
                            <div class="stats-icon" style="background: linear-gradient(135deg, rgba(67, 97, 238, 0.15), rgba(67, 97, 238, 0.25)); color: var(--primary-color);">
                                <i class="fas fa-tasks"></i>
                            </div>
                            <h3 class="stats-number">{stats['total']}</h3>
                            <p class="stats-label">Total Tasks</p>
                            <div class="stats-progress">
                                <div class="stats-progress-bar bg-primary" style="width: 100%"></div>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-2">
                        <div class="stats-card">
                            <div class="stats-icon" style="background: linear-gradient(135deg, rgba(255, 193, 7, 0.15), rgba(255, 193, 7, 0.25)); color: var(--warning-color);">
                                <i class="fas fa-clock"></i>
                            </div>
                            <h3 class="stats-number">{stats['pending']}</h3>
                            <p class="stats-label">Pending</p>
                            <div class="stats-progress">
                                <div class="stats-progress-bar bg-warning" style="width: {stats['pending'] / max(stats['total'], 1) * 100}%"></div>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-2">
                        <div class="stats-card">
                            <div class="stats-icon" style="background: linear-gradient(135deg, rgba(23, 162, 184, 0.15), rgba(23, 162, 184, 0.25)); color: var(--info-color);">
                                <i class="fas fa-spinner"></i>
                            </div>
                            <h3 class="stats-number">{stats['in-progress']}</h3>
                            <p class="stats-label">In Progress</p>
                            <div class="stats-progress">
                                <div class="stats-progress-bar bg-info" style="width: {stats['in-progress'] / max(stats['total'], 1) * 100}%"></div>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-2">
                        <div class="stats-card {'overdue' if stats['overdue'] > 0 else ''}">
                            <div class="stats-icon" style="background: linear-gradient(135deg, rgba(231, 76, 60, 0.15), rgba(231, 76, 60, 0.25)); color: var(--overdue-color);">
                                <i class="fas fa-exclamation-triangle"></i>
                            </div>
                            <h3 class="stats-number">{stats['overdue']}</h3>
                            <p class="stats-label">Overdue</p>
                            <div class="stats-progress">
                                <div class="stats-progress-bar bg-danger" style="width: {stats['overdue'] / max(stats['total'], 1) * 100}%"></div>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="stats-card {'due-today' if stats['due_today'] > 0 else ''}">
                            <div class="stats-icon" style="background: linear-gradient(135deg, rgba(243, 156, 18, 0.15), rgba(243, 156, 18, 0.25)); color: var(--due-today-color);">
                                <i class="fas fa-calendar-day"></i>
                            </div>
                            <h3 class="stats-number">{stats['due_today']}</h3>
                            <p class="stats-label">Due Today</p>
                            <div class="stats-progress">
                                <div class="stats-progress-bar" style="width: {stats['due_today'] / max(stats['total'], 1) * 100}%; background: var(--due-today-color);"></div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Main Content -->
                <div class="row">
                    <div class="col-lg-8">
                        <div class="card">
                            <div class="card-header d-flex justify-content-between align-items-center">
                                <div>
                                    <h5 class="mb-0">
                                        <i class="fas fa-calendar-alt me-2"></i>Recent Tasks
                                        <small class="text-muted ms-2">(Due dates highlighted)</small>
                                    </h5>
                                </div>
                                <div class="d-flex gap-2">
                                    <button class="btn btn-sm btn-outline-primary" onclick="refreshDashboard()" title="Refresh">
                                        <i class="fas fa-sync-alt"></i>
                                    </button>
                                    <button class="btn btn-sm btn-primary" onclick="createTask()">
                                        <i class="fas fa-plus me-1"></i>New Task
                                    </button>
                                </div>
                            </div>
                            <div class="card-body">
                                <div id="tasksList">
                                    <!-- Tasks will be loaded here -->
                                </div>
                            </div>
                        </div>
                    </div>

                    <div class="col-lg-4">
                        <div class="card mb-3">
                            <div class="card-header">
                                <h5 class="mb-0"><i class="fas fa-bolt me-2"></i>Quick Actions</h5>
                            </div>
                            <div class="card-body">
                                <div class="d-grid gap-3">
                                    <a href="tasks.py?user_id={user['id']}" class="btn btn-outline-primary btn-lg d-flex align-items-center justify-content-center">
                                        <i class="fas fa-list me-2"></i>View All Tasks
                                    </a>
                                    <button class="btn btn-outline-success btn-lg d-flex align-items-center justify-content-center" onclick="createTask()">
                                        <i class="fas fa-plus-circle me-2"></i>Create New Task
                                    </button>
                                    <button class="btn btn-outline-info btn-lg d-flex align-items-center justify-content-center" onclick="refreshDashboard()">
                                        <i class="fas fa-sync-alt me-2"></i>Refresh Dashboard
                                    </button>
                                    <button class="btn btn-outline-warning btn-lg d-flex align-items-center justify-content-center" onclick="showDueTasks()">
                                        <i class="fas fa-calendar-exclamation me-2"></i>Due Tasks
                                    </button>
                                </div>
                            </div>
                        </div>

                        <div class="card user-info-card">
                            <div class="card-header">
                                <h5 class="mb-0"><i class="fas fa-user-circle me-2"></i>Your Profile</h5>
                            </div>
                            <div class="card-body">
                                <p><i class="fas fa-user"></i> <strong>{user['name']}</strong></p>
                                <p><i class="fas fa-envelope"></i> {user['email']}</p>
                                <p><i class="fas fa-id-card"></i> ID: <code>{user['id']}</code></p>
                                <p><i class="fas fa-bell"></i> 
                                    <span class="badge bg-primary">Reminders Active</span>
                                    <small class="text-muted d-block mt-1">Email alerts for due tasks</small>
                                </p>
                                <div class="mt-3">
                                    <button class="btn btn-sm btn-outline-primary w-100" onclick="showProfile()">
                                        <i class="fas fa-cog me-1"></i>Manage Profile
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Create Task Modal -->
            <div class="modal fade" id="createTaskModal" tabindex="-1">
                <div class="modal-dialog">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title"><i class="fas fa-plus-circle me-2"></i>Create New Task</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <form id="taskForm">
                                <div class="mb-3">
                                    <label class="form-label">Task Title *</label>
                                    <input type="text" id="taskTitle" class="form-control" 
                                           placeholder="What needs to be done?" required maxlength="255">
                                    <small class="text-muted">Maximum 255 characters</small>
                                </div>

                                <div class="mb-3">
                                    <label class="form-label">Description</label>
                                    <textarea id="taskDescription" class="form-control" rows="3" 
                                              placeholder="Add details, notes, or requirements..."></textarea>
                                </div>

                                <div class="row">
                                    <div class="col-md-6 mb-3">
                                        <label class="form-label">Status</label>
                                        <select id="taskStatus" class="form-select">
                                            <option value="Pending">Pending</option>
                                            <option value="In-Progress">In Progress</option>
                                            <option value="Completed">Completed</option>
                                        </select>
                                    </div>
                                    <div class="col-md-6 mb-3">
                                        <label class="form-label">Priority</label>
                                        <select id="taskPriority" class="form-select">
                                            <option value="low">Low</option>
                                            <option value="medium" selected>Medium</option>
                                            <option value="high">High</option>
                                            <option value="urgent">Urgent</option>
                                        </select>
                                    </div>
                                </div>

                                <div class="mb-3">
                                    <label class="form-label">
                                        <i class="fas fa-calendar-alt me-1"></i>Due Date
                                    </label>
                                    <input type="date" id="taskDueDate" class="form-control" 
                                           placeholder="Select a date (optional)">
                                    <small class="text-muted">Leave empty for no deadline</small>
                                </div>
                            </form>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">
                                <i class="fas fa-times me-1"></i>Cancel
                            </button>
                            <button type="button" class="btn btn-primary" onclick="saveTask()">
                                <i class="fas fa-save me-1"></i>Save Task
                            </button>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Bootstrap JS Bundle -->
            <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
            <!-- Flatpickr for date picker -->
            <script src="https://cdn.jsdelivr.net/npm/flatpickr"></script>

            <script>
    const userId = '{user['id']}';
    const recentTasks = {recent_tasks_json};

    document.addEventListener('DOMContentLoaded', function() {{
      displayTasks();
    }});

    function displayTasks() {{
      const container = document.getElementById('tasksList');
      if (!recentTasks || recentTasks.length === 0) {{
        container.innerHTML = '<div class="empty-state"><i class="fas fa-tasks fa-4x"></i><h3 class="mt-4">No tasks yet</h3><p class="text-muted mb-4">Get started by creating your first task</p><button class="btn btn-primary btn-lg" onclick="createTask()"><i class="fas fa-plus me-2"></i>Create Your First Task</button></div>';
        return;
      }}
      let html = '';
      recentTasks.forEach(task => {{
        let dueClass = '';
        let dueBadge = '';
        if (task.due_date) {{
          const dueDate = new Date(task.due_date);
          const today = new Date(); today.setHours(0,0,0,0); dueDate.setHours(0,0,0,0);
          if (dueDate < today && task.status !== 'Completed') {{ dueClass = 'overdue'; dueBadge = '<span class="badge bg-danger ms-2">Overdue</span>'; }}
          else if (dueDate.getTime() === today.getTime() && task.status !== 'Completed') {{ dueClass = 'due-today'; dueBadge = '<span class="badge bg-warning ms-2">Due Today</span>'; }}
          else if (dueDate > today) {{ dueClass = 'upcoming'; dueBadge = '<span class="badge bg-info ms-2">Upcoming</span>'; }}
        }} else {{ dueClass = 'no-due'; dueBadge = '<span class="badge bg-secondary ms-2">No Deadline</span>'; }}

        let statusBadge = '';
        switch(task.status) {{
            case 'Pending': statusBadge = '<span class="badge bg-warning">Pending</span>'; break;
            case 'In-Progress': statusBadge = '<span class="badge bg-info">In Progress</span>'; break;
            case 'Completed': statusBadge = '<span class="badge bg-success">Completed</span>'; break;
        }}
        let priorityBadge = '';
        switch(task.priority) {{
            case 'low': priorityBadge = '<span class="badge bg-success">Low</span>'; break;
            case 'medium': priorityBadge = '<span class="badge bg-info">Medium</span>'; break;
            case 'high': priorityBadge = '<span class="badge bg-warning">High</span>'; break;
            case 'urgent': priorityBadge = '<span class="badge bg-danger">Urgent</span>'; break;
            default: priorityBadge = '<span class="badge bg-secondary">' + (task.priority || 'Medium') + '</span>';
        }}

        // NOTE: add data-task-id and id attribute to each task-card so deletion is reliable
        html += '<div class="task-card ' + dueClass + '" data-task-id="' + task.id + '" id="task-' + task.id + '">' +
                '<div class="d-flex justify-content-between align-items-start">' +
                '<div class="flex-grow-1">' +
                '<h6 class="mb-1">' + escapeHtml(task.title) + '</h6>' +
                '<p class="text-muted small mb-2">' + (task.description || 'No description') + '</p>' +
                '<div class="d-flex gap-2 mb-2">' + statusBadge + priorityBadge + dueBadge + '</div>' +
                '<small class="text-muted">Created: ' + (task.created_at || 'N/A') + '</small>' +
                (task.due_date ? '<small class="text-muted ms-3">Due: ' + new Date(task.due_date).toLocaleDateString() + '</small>' : '') +
                '</div>' +
                '<div class="task-actions">' +
                '<button class="action-btn btn-edit" onclick="editTask(' + task.id + ')" title="Edit"><i class="fas fa-edit"></i></button>' +
                '<button class="action-btn btn-delete" onclick="deleteTask(' + task.id + ')" title="Delete"><i class="fas fa-trash"></i></button>' +
                '</div></div></div>';
      }});
      container.innerHTML = html;
    }}

    function createTask() {{
      const modal = new bootstrap.Modal(document.getElementById('createTaskModal'));
      modal.show();
    }}

    function saveTask() {{
      const title = document.getElementById('taskTitle').value.trim();
      const description = document.getElementById('taskDescription').value;
      const status = document.getElementById('taskStatus').value;
      const priority = document.getElementById('taskPriority').value;
      const dueDate = document.getElementById('taskDueDate').value;
      if (!title) {{ alert('Please enter a task title'); return; }}
      showLoading();
      const formData = new FormData();
      formData.append('user_id', userId);
      formData.append('title', title);
      formData.append('description', description);
      formData.append('status', status);
      formData.append('priority', priority);
      formData.append('due_date', dueDate);
      formData.append('action', 'create');

      fetch('dashboard.py?action=create', {{
        method: 'POST',
        body: formData
      }})
      .then(response => response.json())
      .then(data => {{
        hideLoading();
        if (data.success) {{
          alert('Task created successfully!');
          const modal = bootstrap.Modal.getInstance(document.getElementById('createTaskModal'));
          if (modal) modal.hide();
          document.getElementById('taskForm').reset();
          // reload to show new task (alternative: call list API and re-render)
          setTimeout(() => location.reload(), 700);
        }} else {{
          alert('Error: ' + data.error);
        }}
      }})
      .catch(err => {{
        hideLoading();
        console.error(err);
        alert('Failed to save task: ' + err.message);
      }});
    }}

    function editTask(taskId) {{
      window.location.href = 'tasks.py?user_id=' + userId + '&edit=' + taskId;
    }}

    // Improved delete: calls server API to delete from DB, then removes the task card from DOM
    function deleteTask(taskId) {{
      if (!confirm('Are you sure you want to delete this task?')) return;
      taskId = String(taskId).trim();
    if (!/^\d+$/.test(taskId)) {{
    alert('Invalid task id (client-side).');
        return;
    }}

      showLoading();
      const formData = new FormData();
      formData.append('id', taskId);
      formData.append('action', 'delete');
      formData.append('user_id', userId);

      fetch('dashboard.py?action=delete&id=' + encodeURIComponent(taskId), {{
        method: 'POST',
        body: formData
      }})
      .then(response => {{
        const ct = response.headers.get('content-type') || '';
        if (ct.indexOf('application/json') === -1) {{
          return response.text().then(txt => {{ throw new Error('Server returned unexpected response'); }});
        }}
        return response.json();
      }})
      .then(data => {{
        hideLoading();
        if (data.success) {{
          const deletedId = String(data.deleted_id || taskId);
          let el = document.querySelector('[data-task-id="' + deletedId + '"]');
          if (!el) el = document.getElementById('task-' + deletedId);
          if (!el) {{
            // attempt to find via delete button attribute
            const candidate = document.querySelector('.task-card button.action-btn.btn-delete[onclick*="deleteTask(' + deletedId + ')"]');
            if (candidate) el = candidate.closest('.task-card');
          }}
          if (el) {{
            el.remove();
          }} else {{
            // fallback: reload page
            location.reload();
            return;
          }}

          // update simple stat: total tasks
          try {{
            const totalEl = document.getElementById('stat-total');
            if (totalEl) {{
              const cur = parseInt(totalEl.textContent.trim() || '0', 10);
              totalEl.textContent = Math.max(0, cur - 1);
            }}
            // optionally update others (pending/inprogress/overdue) by reloading or calling list API for complete accuracy
          }} catch(e) {{
            console.warn('Failed to update stats in DOM:', e);
          }}

          showNotification('Task deleted successfully!', 'success');
        }} else {{
          alert('Error: ' + (data.error || 'Unknown error'));
        }}
      }})
      .catch(error => {{
        hideLoading();
        console.error('Failed to delete task:', error);
        alert('Failed to delete task: ' + error.message);
      }});
    }}

    function refreshDashboard() {{
      showLoading();
      setTimeout(() => location.reload(), 400);
    }}

    function showDueTasks() {{
      const dueTasks = recentTasks.filter(task => {{
        if (!task.due_date) return false;
        const dueDate = new Date(task.due_date);
        const today = new Date(); today.setHours(0,0,0,0); dueDate.setHours(0,0,0,0);
        return dueDate <= today && task.status !== 'Completed';
      }});
      if (dueTasks.length === 0) {{
        showNotification('No due or overdue tasks found!', 'info');
        return;
      }}
      let html = '';
      dueTasks.forEach(task => {{
        const dueDate = new Date(task.due_date);
        const today = new Date(); today.setHours(0,0,0,0); dueDate.setHours(0,0,0,0);
        let dueClass = dueDate < today ? 'overdue' : 'due-today';
        let dueBadge = dueDate < today ? '<span class="badge bg-danger ms-2">Overdue</span>' : '<span class="badge bg-warning ms-2">Due Today</span>';
        html += '<div class="task-card ' + dueClass + '" data-task-id="' + task.id + '" id="task-' + task.id + '">' +
                '<div class="d-flex justify-content-between align-items-start">' +
                '<div class="flex-grow-1"><h6 class="mb-1">' + escapeHtml(task.title) + '</h6><p class="text-muted small mb-2">' + (task.description || 'No description') + '</p>' +
                '<div>' + dueBadge + '</div><small class="text-muted">Due: ' + new Date(task.due_date).toLocaleDateString() + '</small></div>' +
                '<div class="task-actions"><button class="action-btn btn-edit" onclick="editTask(' + task.id + ')"><i class="fas fa-edit"></i></button>' +
                '<button class="action-btn btn-delete" onclick="deleteTask(' + task.id + ')"><i class="fas fa-trash"></i></button></div></div></div>';
      }});
      document.getElementById('tasksList').innerHTML = html;
      showNotification('Showing ' + dueTasks.length + ' due/overdue task(s)', 'info');
    }}

    function showProfile() {{ alert('Profile management coming soon'); }}
    function logout() {{ if(confirm('Are you sure you want to logout?')) window.location.href='login.py'; }}
    function escapeHtml(text) {{ if (!text) return ''; const div = document.createElement('div'); div.textContent = text; return div.innerHTML; }}
    function showLoading() {{ document.getElementById('loadingOverlay').style.display = 'flex'; }}
    function hideLoading() {{ document.getElementById('loadingOverlay').style.display = 'none'; }}

    function showNotification(message, type='info') {{
      // use simple alert or a bootstrap toast; keep simple for compatibility
      // For nicer UX, you can implement toasts; for now just console + small overlay
      console.log('[notify]', type, message);
      // quick visual small alert
      const el = document.createElement('div');
      el.className = 'alert alert-' + (type === 'error' ? 'danger' : (type === 'success' ? 'success' : 'info')) + '';
      el.style.position = 'fixed'; el.style.top = '20px'; el.style.right = '20px'; el.style.zIndex = 99999;
      el.textContent = message;
      document.body.appendChild(el);
      setTimeout(()=> el.remove(), 2500);
    }}
  </script>
</body>
</html>
""")

# ----------------- main -----------------
def main():
    try:
        query_string = os.environ.get('QUERY_STRING', '') or ''
        params = parse_qs(query_string)
        if params.get('action', [''])[0]:
            handle_api_request()
            return

        user, error = authenticate_user_by_id()
        if error:
            print("Content-Type: text/html; charset=utf-8")
            print()
            print(f"""<!DOCTYPE html><html><head><script>alert({json.dumps(error)});window.location.href='login.py';</script></head><body>Redirecting...</body></html>""")
            return

        print("Content-Type: text/html; charset=utf-8")
        print()
        # debug comment (safe)
        log_debug("authenticated user = " + json.dumps(user))
        stats_data = get_user_stats(user['id'])
        render_dashboard(user, stats_data)
    except Exception as e:
        tb = traceback.format_exc()
        print("Content-Type: text/html; charset=utf-8")
        print()
        print("<pre style='white-space:pre-wrap; color:#b00; background:#fee; padding:10px;'>")
        print("Internal server error (debug output):\n\n")
        print(tb)
        print("</pre>")

if __name__ == '__main__':
    main()