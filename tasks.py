#!C:/Users/Deepak/AppData/Local/Programs/Python/Python311/python.exe
import cgi
import cgitb
import os
import sys
import json
import pymysql
from urllib.parse import parse_qs
import datetime
import traceback

cgitb.enable()

# Database configuration (update if needed)
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


def get_auth_data():
    """
    Return user_id (string).
    Preference: GET query string first, then POST form fields.
    """
    query_string = os.environ.get('QUERY_STRING', '') or ''
    params = parse_qs(query_string)

    user_id = params.get('user_id', [''])[0] or ''

    # If not in GET, try POST/form
    if not user_id:
        try:
            form = cgi.FieldStorage()
            user_id = form.getvalue('user_id', '') or ''
        except Exception:
            user_id = user_id or ''

    return user_id


def authenticate_user():
    """
    Authenticate by numeric user_id (GET or POST).
    Returns (user_dict, error_message). user_dict contains at least 'id' and 'name'.
    """
    user_id = get_auth_data()

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
            cursor.close()
            conn.close()
        except Exception:
            pass
        return None, f"Database error: {str(e)}"


def get_user_tasks(user_id):
    """Get all tasks for user including due date"""
    try:
        conn = db_connect()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, title, description, status, priority,
                   DATE_FORMAT(created_at, '%%Y-%%m-%%d %%H:%%i:%%s') as created_at,
                   DATE_FORMAT(updated_at, '%%Y-%%m-%%d %%H:%%i:%%s') as updated_at,
                   DATE_FORMAT(due_date, '%%Y-%%m-%%d') as due_date,
                   reminder_sent
            FROM tasks 
            WHERE user_id=%s
            ORDER BY created_at DESC
        """, (user_id,))

        tasks = cursor.fetchall()

        cursor.close()
        conn.close()

        return tasks

    except Exception:
        # avoid crashing; return empty list
        return []


# ---------- JSON update handler ----------
def handle_json_update(body_text):
    """
    Expect JSON like:
    { "user_id": <id>, "id": <task_id>, "title": "...", "description": "...",
      "status": "...", "priority": "...", "due_date": "YYYY-MM-DD" or null,
      "reminder_sent": 0|1 }
    """
    try:
        data = json.loads(body_text)
    except Exception:
        send_json({"ok": False, "error": "Invalid JSON body"}, status=400)
        return

    user_id = data.get('user_id')
    task_id = data.get('id') or data.get('task_id')
    if not user_id or not task_id:
        send_json({"ok": False, "error": "Missing user_id or id"}, status=400)
        return

    try:
        uid = int(user_id)
        tid = int(task_id)
    except Exception:
        send_json({"ok": False, "error": "Invalid user_id or id"}, status=400)
        return

    # Gather update fields (use defaults consistent with your schema)
    title = data.get('title') or ''
    description = data.get('description') or None
    status = data.get('status') or 'Pending'
    priority = data.get('priority') or 'medium'
    due_date = data.get('due_date')  # may be None or '' to clear
    reminder_sent = 1 if data.get('reminder_sent') in (1, '1', True, 'true') else 0

    # Normalize due_date to None when empty
    if due_date in (None, '', 'null'):
        due_date_val = None
    else:
        due_date_val = due_date  # expecting 'YYYY-MM-DD'

    try:
        conn = db_connect()
        cur = conn.cursor()

        # Verify task belongs to user
        cur.execute("SELECT id FROM tasks WHERE id=%s AND user_id=%s LIMIT 1", (tid, uid))
        row = cur.fetchone()
        if not row:
            cur.close()
            conn.close()
            send_json({"ok": False, "error": "Task not found or not owned by user"}, status=403)
            return

        # Update row
        cur.execute("""
            UPDATE tasks
               SET title=%s,
                   description=%s,
                   status=%s,
                   priority=%s,
                   due_date=%s,
                   reminder_sent=%s,
                   updated_at=NOW()
             WHERE id=%s
        """, (title, description, status, priority, due_date_val, reminder_sent, tid))

        # Return updated row
        cur.execute("""
            SELECT id, title, description, status, priority,
                   DATE_FORMAT(created_at, '%%Y-%%m-%%d %%H:%%i:%%s') as created_at,
                   DATE_FORMAT(updated_at, '%%Y-%%m-%%d %%H:%%i:%%s') as updated_at,
                   DATE_FORMAT(due_date, '%%Y-%%m-%%d') as due_date,
                   reminder_sent
            FROM tasks WHERE id=%s LIMIT 1
        """, (tid,))
        updated = cur.fetchone()
        cur.close()
        conn.close()

        send_json({"ok": True, "task": updated})
        return

    except Exception as e:
        try:
            cur.close()
            conn.close()
        except Exception:
            pass
        send_json({"ok": False, "error": "Server error", "exception": str(e)}, status=500)
        return


# ---------- helper to send JSON ----------
def send_json(obj, status=200):
    if status != 200:
        print(f"Status: {status} {http_status_text(status)}")
    print("Content-Type: application/json; charset=utf-8")
    print()
    sys.stdout.write(json.dumps(obj, default=str))
    sys.stdout.flush()


def http_status_text(code):
    return {
        200: "OK",
        400: "Bad Request",
        401: "Unauthorized",
        403: "Forbidden",
        404: "Not Found",
        500: "Internal Server Error"
    }.get(code, "")


# ---------- render page (almost same as your previous render) ----------
def render_tasks_page(user, tasks):
    tasks_json = json.dumps(tasks, default=str)
    user_name = str(user.get('name', ''))
    user_id = str(user.get('id', ''))

    print("Content-Type: text/html; charset=utf-8")
    print()
    # (HTML is similar to your previous one; client-side updateTask now POSTs to same script)
    print(f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Task Management - Task Tracker</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/flatpickr/dist/flatpickr.min.css">
  <style>
    /* keep your styles (omitted here for brevity in explanation) */
    :root{{--primary-color:#4361ee;--secondary-color:#3a0ca3;--danger-color:#dc3545;--warning-color:#ffc107;--info-color:#17a2b8;--success-color:#28a745}}
    body{{font-family:'Segoe UI',Tahoma, Geneva, Verdana, sans-serif;background-color:#f8f9fa}}
    .navbar{{background:linear-gradient(to right,var(--primary-color),var(--secondary-color));box-shadow:0 2px 10px rgba(0,0,0,0.1)}}
    .task-table{{background:white;border-radius:10px;overflow:hidden;box-shadow:0 3px 15px rgba(0,0,0,0.05)}}
    .task-table thead th{{background-color:#f8f9fa;border-bottom:2px solid #dee2e6;font-weight:600;color:#495057}}
    .task-table tbody tr:hover{{background-color:rgba(67,97,238,0.05)}}
    .status-badge{{padding:4px 12px;border-radius:20px;font-size:0.85rem;font-weight:500;display:inline-block;min-width:100px;text-align:center}}
    .priority-badge{{padding:3px 8px;border-radius:12px;font-size:0.75rem;font-weight:600}}
    .due-date-badge{{padding:4px 10px;border-radius:15px;font-size:0.8rem;font-weight:500}}
    .due-date-overdue{{background-color:#f8d7da;color:#721c24;border-left:3px solid var(--danger-color)}}
    .due-date-today{{background-color:#fff3cd;color:#856404;border-left:3px solid var(--warning-color)}}
    .due-date-upcoming{{background-color:#d1ecf1;color:#0c5460;border-left:3px solid var(--info-color)}}
    .due-date-none{{background-color:#e9ecef;color:#495057}}
    .empty-state{{text-align:center;padding:60px 20px}}
    .filter-buttons .btn{{margin-right:5px;margin-bottom:5px}}
    .task-row.overdue{{background-color:rgba(220,53,69,0.05)!important}}
    .task-row.due-today{{background-color:rgba(255,193,7,0.05)!important}}
  </style>
</head>
<body>
<nav class="navbar navbar-expand-lg navbar-dark">
  <div class="container">
    <a class="navbar-brand" href="#"><i class="fas fa-tasks me-2"></i>Task Tracker</a>
    <div class="navbar-text text-white">
      <span class="me-3" id="navbarUserName">User</span>
      <a id="dashboardLink" href="#" class="btn btn-sm btn-outline-light me-2"><i class="fas fa-tachometer-alt me-1"></i>Dashboard</a>
      <button class="btn btn-sm btn-outline-light" onclick="logout()"><i class="fas fa-sign-out-alt me-1"></i>Logout</button>
    </div>
  </div>
</nav>

<div class="container mt-4">
  <div class="row mb-4">
    <div class="col-md-8">
      <h2>Task Management</h2>
      <p class="text-muted">Manage all your tasks in one place</p>
    </div>
    <div class="col-md-4 text-end">
      <button class="btn btn-primary" onclick="showCreateModal()"><i class="fas fa-plus me-2"></i>Add New Task</button>
      <button class="btn btn-outline-secondary ms-2" onclick="refreshTasks()"><i class="fas fa-sync-alt"></i></button>
    </div>
  </div>

  <div class="row mb-3"><div class="col-12">
    <div class="filter-buttons">
      <button class="btn btn-outline-primary active" onclick="filterTasks('all', event)">All Tasks</button>
      <button class="btn btn-outline-warning" onclick="filterTasks('Pending', event)"><i class="fas fa-clock me-1"></i>Pending</button>
      <button class="btn btn-outline-info" onclick="filterTasks('In-Progress', event)"><i class="fas fa-spinner me-1"></i>In Progress</button>
      <button class="btn btn-outline-success" onclick="filterTasks('Completed', event)"><i class="fas fa-check-circle me-1"></i>Completed</button>
      <button class="btn btn-outline-danger" onclick="filterTasks('overdue', event)"><i class="fas fa-exclamation-circle me-1"></i>Overdue</button>
    </div>
  </div></div>

  <div class="card">
    <div class="card-header d-flex justify-content-between align-items-center">
      <span>All Tasks</span><span class="badge bg-primary" id="taskCount">0 tasks</span>
    </div>
    <div class="card-body p-0">
      <div id="tasksContainer"></div>
    </div>
  </div>
</div>

<!-- Create Modal -->
<div class="modal fade" id="createTaskModal" tabindex="-1"><div class="modal-dialog modal-lg"><div class="modal-content">
  <div class="modal-header"><h5 class="modal-title"><i class="fas fa-plus-circle me-2"></i>Create New Task</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div>
  <div class="modal-body"><form id="createTaskForm">
    <div class="mb-3"><label class="form-label">Task Title *</label><input type="text" id="createTitle" class="form-control" maxlength="255" required></div>
    <div class="mb-3"><label class="form-label">Due Date</label><input type="date" id="createDueDate" class="form-control"></div>
  </form></div>
  <div class="modal-footer"><button class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button><button class="btn btn-primary" onclick="createTask()">Create Task</button></div>
</div></div></div>

<!-- Edit Modal -->
<div class="modal fade" id="editTaskModal" tabindex="-1"><div class="modal-dialog modal-lg"><div class="modal-content">
  <div class="modal-header"><h5 class="modal-title"><i class="fas fa-edit me-2"></i>Edit Task</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div>
  <div class="modal-body"><form id="editTaskForm">
    <input type="hidden" id="editTaskId">
    <div class="mb-3"><label class="form-label">Task Title *</label><input type="text" id="editTitle" class="form-control" maxlength="255" required></div>
    <div class="mb-3"><label class="form-label">Description</label><textarea id="editDescription" class="form-control" rows="4"></textarea></div>
    <div class="row">
      <div class="col-md-6 mb-3"><label class="form-label">Status</label>
        <select id="editStatus" class="form-select"><option value="Pending">Pending</option><option value="In-Progress">In Progress</option><option value="Completed">Completed</option></select></div>
      <div class="col-md-6 mb-3"><label class="form-label">Priority</label>
        <select id="editPriority" class="form-select"><option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option><option value="urgent">Urgent</option></select></div>
    </div>
    <div class="row">
      <div class="col-md-6 mb-3"><label class="form-label">Due Date</label><input type="date" id="editDueDate" class="form-control"></div>
      <div class="col-md-6 mb-3"><label class="form-label">Created At (read-only)</label><input type="text" id="editCreatedAt" class="form-control" readonly></div>
    </div>
    <div class="form-check mb-3"><input class="form-check-input" type="checkbox" value="1" id="editReminderSent"><label class="form-check-label" for="editReminderSent">Reminder sent</label></div>
  </form></div>
  <div class="modal-footer"><button class="btn btn-secondary" data-bs-dismiss="modal"><i class="fas fa-times me-1"></i>Cancel</button><button class="btn btn-primary" onclick="updateTask()"><i class="fas fa-save me-1"></i>Save Changes</button></div>
</div></div></div>

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/flatpickr"></script>

<script>
  // injected server data
  const USER_ID = {json.dumps(user_id)};
  const USER_NAME = {json.dumps(user_name)};
  const TASKS_FROM_SERVER = {tasks_json};

  document.getElementById('navbarUserName').textContent = USER_NAME || 'User';
  document.getElementById('dashboardLink').href = 'dashboard.py?user_id=' + encodeURIComponent(USER_ID);

  let allTasks = Array.isArray(TASKS_FROM_SERVER) ? TASKS_FROM_SERVER : [];
  let currentFilter = 'all';

  document.addEventListener('DOMContentLoaded', () => {{
    flatpickr("#createDueDate", {{ dateFormat: "Y-m-d", minDate: "today", disableMobile: true }});
    flatpickr("#editDueDate", {{ dateFormat: "Y-m-d", minDate: "today", disableMobile: true }});
    displayTasks();
  }});

  function getDueDateStatus(dueDate) {{
    if (!dueDate) return 'none';
    const today = new Date(); today.setHours(0,0,0,0);
    const due = new Date(dueDate); due.setHours(0,0,0,0);
    const diffDays = Math.floor((due - today) / (1000*60*60*24));
    if (diffDays < 0) return 'overdue';
    if (diffDays === 0) return 'today';
    if (diffDays <= 7) return 'upcoming';
    return 'future';
  }}

  function getDueDateBadge(dueDate) {{
    const status = getDueDateStatus(dueDate);
    const icons = {{ overdue:'fas fa-exclamation-circle', today:'fas fa-calendar-day', upcoming:'fas fa-calendar-check', future:'far fa-calendar', none:'far fa-calendar-times' }};
    const texts  = {{ overdue:'OVERDUE', today:'TODAY', upcoming:'UPCOMING', future:'FUTURE', none:'NO DEADLINE' }};
    const classes= {{ overdue:'due-date-overdue', today:'due-date-today', upcoming:'due-date-upcoming', future:'due-date-upcoming', none:'due-date-none' }};
    return '<span class="due-date-badge ' + classes[status] + '" title="' + (dueDate ? 'Due: ' + new Date(dueDate).toLocaleDateString() : 'No deadline') + '">' +
           '<i class="' + icons[status] + ' me-1"></i>' + (dueDate ? new Date(dueDate).toLocaleDateString() : texts[status]) + '</span>';
  }}

  function displayTasks() {{
    const container = document.getElementById('tasksContainer');
    let filteredTasks = allTasks;

    if (currentFilter !== 'all') {{
        if (currentFilter === 'overdue') {{
            filteredTasks = allTasks.filter(task => {{
                if (!task.due_date) return false;
                const today = new Date(); today.setHours(0,0,0,0);
                const due = new Date(task.due_date); due.setHours(0,0,0,0);
                return due < today && task.status !== 'Completed';
            }});
        }} else {{
            filteredTasks = allTasks.filter(task => task.status === currentFilter);
        }}
    }}

    document.getElementById('taskCount').textContent = filteredTasks.length + ' task' + (filteredTasks.length !== 1 ? 's' : '');

    if (filteredTasks.length === 0) {{
        container.innerHTML = '<div class="empty-state"><i class="fas fa-tasks"></i><h4>No tasks found</h4><p class="text-muted">Create a new task to get started</p><button class="btn btn-primary" onclick="showCreateModal()"><i class="fas fa-plus me-2"></i>Create New Task</button></div>';
        return;
    }}

    let html = '<div class="table-responsive"><table class="table table-hover mb-0 task-table"><thead><tr><th>#</th><th>Task</th><th>Description</th><th>Status</th><th>Priority</th><th>Due Date</th><th>Created</th><th class="text-center">Actions</th></tr></thead><tbody>';

    filteredTasks.forEach((task, index) => {{
        const dueStatus = getDueDateStatus(task.due_date);
        const rowClass = dueStatus === 'overdue' ? 'overdue' : (dueStatus === 'today' ? 'due-today' : '');
        const statusClass = (task.status || '').toString().toLowerCase().replace(/ /g, '-');
        html += '<tr class="task-row ' + rowClass + '">';
        html += '<td>' + (index + 1) + '</td>';
        html += '<td><strong>' + escapeHtml(task.title || '') + '</strong></td>';
        html += '<td class="small text-muted">' + escapeHtml(task.description || '') + '</td>';
        html += '<td><span class="status-badge badge-' + statusClass + '">' + (task.status || '') + '</span></td>';
        html += '<td>' + (task.priority ? '<span class="priority-badge ' + (task.priority === 'low' ? 'priority-low' : task.priority === 'high' ? 'priority-high' : task.priority === 'urgent' ? 'priority-urgent' : 'priority-medium') + '\\">' + escapeHtml(task.priority) + '</span>' : '') + '</td>';
        html += '<td>' + getDueDateBadge(task.due_date) + '</td>';
        html += '<td class="small">' + (task.created_at || '') + '</td>';
        html += '<td class="text-center"><button class="btn btn-sm btn-outline-primary me-1" onclick="editTaskModalByIndex(' + index + ')"><i class="fas fa-edit"></i></button>';
        html += '<button class="btn btn-sm btn-outline-danger" onclick="deleteTask(' + (task.id ? task.id : ('\\'idx-' + index + '\\'')) + ', \\'' + escapeHtml(task.title || '') + '\\')"><i class="fas fa-trash"></i></button></td></tr>';
    }});

    html += '</tbody></table></div>';
    container.innerHTML = html;
  }}

  function filterTasks(filter, evt) {{
    currentFilter = filter;
    document.querySelectorAll('.filter-buttons .btn').forEach(btn => {{
        btn.classList.remove('active', 'btn-primary');
        btn.classList.add('btn-outline-primary');
    }});
    try {{
        const button = (evt && evt.target) ? evt.target.closest('button') : null;
        if (button) {{
            button.classList.add('active', 'btn-primary');
            button.classList.remove('btn-outline-primary');
        }}
    }} catch(e){{}}
    displayTasks();
  }}

  function showCreateModal() {{
    document.getElementById('createTaskForm').reset();
    const modal = new bootstrap.Modal(document.getElementById('createTaskModal'));
    modal.show();
  }}

  async function createTask() {{
    const title = document.getElementById('createTitle').value.trim();
    const dueDate = document.getElementById('createDueDate').value;
    if (!title) {{ alert('Please enter a task title'); return; }}

    // Client-only for now (you can add server persist later)
    const newTask = {{
        id: Date.now(), title, description: '', status: 'Pending', priority: 'medium', due_date: dueDate, created_at: new Date().toISOString().slice(0,19).replace('T',' ')
    }};
    allTasks.unshift(newTask);
    displayTasks();
    const modal = bootstrap.Modal.getInstance(document.getElementById('createTaskModal'));
    if (modal) modal.hide();
  }}

  function editTaskModalByIndex(filteredIndex) {{
    let filteredTasks = allTasks;
    if (currentFilter !== 'all') {{
        if (currentFilter === 'overdue') {{
            filteredTasks = allTasks.filter(task => {{
                if (!task.due_date) return false;
                const today = new Date(); today.setHours(0,0,0,0);
                const due = new Date(task.due_date); due.setHours(0,0,0,0);
                return due < today && task.status !== 'Completed';
            }});
        }} else {{
            filteredTasks = allTasks.filter(task => task.status === currentFilter);
        }}
    }}

    const task = filteredTasks[filteredIndex];
    if (!task) return alert('Task not found');

    const idx = allTasks.findIndex(t => String(t.id) === String(task.id));
    if (idx === -1) return alert('Task not found in internal list');

    document.getElementById('editTaskId').value = allTasks[idx].id;
    document.getElementById('editTitle').value = allTasks[idx].title || '';
    document.getElementById('editDescription').value = allTasks[idx].description || '';
    document.getElementById('editStatus').value = allTasks[idx].status || 'Pending';
    document.getElementById('editPriority').value = allTasks[idx].priority || 'medium';
    document.getElementById('editDueDate').value = allTasks[idx].due_date || '';
    document.getElementById('editCreatedAt').value = allTasks[idx].created_at || '';
    document.getElementById('editReminderSent').checked = !!(allTasks[idx].reminder_sent || allTasks[idx].reminderSent || false);

    const modalEl = document.getElementById('editTaskModal');
    modalEl.dataset.taskIndex = idx;
    const modal = new bootstrap.Modal(modalEl);
    modal.show();
  }}

  async function updateTask() {{
    const modalEl = document.getElementById('editTaskModal');
    const idx = modalEl.dataset.taskIndex !== undefined ? parseInt(modalEl.dataset.taskIndex, 10) : -1;
    if (idx === -1 || !allTasks[idx]) {{
        alert('Internal error: task index not found');
        return;
    }}

    const id = document.getElementById('editTaskId').value;
    const title = document.getElementById('editTitle').value.trim();
    const description = document.getElementById('editDescription').value.trim();
    const status = document.getElementById('editStatus').value;
    const priority = document.getElementById('editPriority').value;
    const dueDate = document.getElementById('editDueDate').value || null;
    const reminderSent = document.getElementById('editReminderSent').checked ? 1 : 0;

    if (!title) {{ alert('Task title cannot be empty'); return; }}

    // Optimistic update
    allTasks[idx].title = title;
    allTasks[idx].description = description;
    allTasks[idx].status = status;
    allTasks[idx].priority = priority;
    allTasks[idx].due_date = dueDate;
    allTasks[idx].reminder_sent = reminderSent;
    allTasks[idx].updated_at = new Date().toISOString().slice(0,19).replace('T',' ');

    displayTasks();
    const modal = bootstrap.Modal.getInstance(modalEl);
    if (modal) modal.hide();

    // Persist to server by POSTing JSON to the same CGI script URL.
    try {{
        const resp = await fetch(window.location.pathname + window.location.search, {{
            method: 'POST',
            headers: {{ 'Content-Type': 'application/json' }},
            body: JSON.stringify({{
                user_id: USER_ID,
                id: id,
                title: title,
                description: description,
                status: status,
                priority: priority,
                due_date: dueDate,
                reminder_sent: reminderSent
            }})
        }});

        const result = await resp.json();
        if (!resp.ok || !result.ok) {{
            console.error('Server update failed', result);
            alert('Could not save changes to server. Changes may not be persisted.');
            return;
        }}

        if (result.task) {{
            // Replace local with server authoritative object (keeps timestamps consistent)
            allTasks[idx] = result.task;
            displayTasks();
        }}
    }} catch (err) {{
        console.error('Network error while saving task', err);
        alert('Network error while saving task. Please check your connection.');
    }}
  }}

  async function deleteTask(id, title) {{
    if (!confirm('Are you sure you want to delete task: \"' + title + '\"?')) return;
    allTasks = allTasks.filter(t => String(t.id) !== String(id));
    displayTasks();
  }}

  function refreshTasks() {{
    displayTasks();
  }}

  function logout() {{
    if (confirm('Are you sure you want to logout?')) {{
      window.location.href = 'login.py';
    }}
  }}

  function escapeHtml(text) {{
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }}
</script>
</body>
</html>""")

# ---------- main ----------
def main():
    try:
        method = os.environ.get('REQUEST_METHOD', 'GET').upper()
        content_type = (os.environ.get('CONTENT_TYPE') or '').lower()

        # If JSON POST, handle update
        if method == 'POST' and 'application/json' in content_type:
            length = int(os.environ.get('CONTENT_LENGTH', 0) or 0)
            body = sys.stdin.read(length) if length else ''
            handle_json_update(body)
            return

        # Otherwise render page
        user, error = authenticate_user()
        if error:
            print("Content-Type: text/html; charset=utf-8")
            print()
            print(f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>Redirecting</title></head><body><script>alert({json.dumps(error)});window.location.href='login.py';</script><p>Redirecting to login...</p></body></html>""")
            return

        tasks = get_user_tasks(user['id'])
        render_tasks_page(user, tasks)

    except Exception:
        print("Content-Type: text/html; charset=utf-8")
        print()
        print("<pre style='white-space:pre-wrap; color:#b00; background:#fee; padding:10px;'>")
        print("Internal server error (debug output):\n\n")
        print(traceback.format_exc())
        print("</pre>")


if __name__ == '__main__':
    main()
