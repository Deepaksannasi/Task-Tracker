#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import json
import cgi
from urllib.parse import parse_qs
import pymysql

# Configuration
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': '',
    'database': 'task',
    'port': 3306
}

DEBUG = False  # Set to True to print helpful debug info to stderr

#  Helpers
def debug(*args, **kwargs):
    if DEBUG:
        print("<!-- DEBUG:", *args, "-->", file=sys.stderr, **kwargs)

def db_connect():
    """Connect to MySQL database"""
    try:
        return pymysql.connect(
            host=DB_CONFIG['host'],
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password'],
            database=DB_CONFIG['database'],
            port=DB_CONFIG['port'],
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=True
        )
    except Exception as e:
        debug("DB Error:", e)
        return None

def json_print(obj):
    """Print JSON response with header (and exit)"""
    # Ensure single Content-Type header
    sys.stdout.write("Content-Type: application/json; charset=utf-8\r\n\r\n")
    sys.stdout.write(json.dumps(obj, default=str))
    sys.stdout.flush()

def authenticate_token(token):
    """Return user id for a valid token, or None."""
    if not token:
        return None
    try:
        conn = db_connect()
        if not conn:
            return None
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE api_token=%s LIMIT 1", (token,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        return user['id'] if user else None
    except Exception as e:
        debug("Auth Error:", e)
        return None

# Request parsing
def read_request():

    method = os.environ.get('REQUEST_METHOD', 'GET').upper()
    qs = os.environ.get('QUERY_STRING', '') or ''
    query = parse_qs(qs)

    # Build headers (simple mapping from environ)
    headers = {}
    for k, v in os.environ.items():
        if k.startswith('HTTP_'):
            headers[k[5:].replace('_', '-').title()] = v
    # CONTENT_TYPE and CONTENT_LENGTH aren't under HTTP_
    if 'CONTENT_TYPE' in os.environ:
        headers['Content-Type'] = os.environ.get('CONTENT_TYPE', '')
    if 'CONTENT_LENGTH' in os.environ:
        headers['Content-Length'] = os.environ.get('CONTENT_LENGTH', '')

    post = {}
    raw_json = False

    # Only parse body for POST/PUT/PATCH
    if method in ('POST', 'PUT', 'PATCH'):
        content_type = (os.environ.get('CONTENT_TYPE') or '').lower()
        content_length = int(os.environ.get('CONTENT_LENGTH') or 0)

        # If JSON, read raw and parse
        if content_type.startswith('application/json'):
            raw = ''
            if content_length > 0:
                try:
                    raw = sys.stdin.read(content_length)
                except Exception as e:
                    debug("Error reading raw JSON body:", e)
            if raw:
                try:
                    post = json.loads(raw)
                    raw_json = True
                    debug("Parsed JSON body:", post)
                except Exception as e:
                    debug("JSON decode error:", e)
                    post = {}
            else:
                post = {}
        else:
            # For form POSTs (multipart/form-data or application/x-www-form-urlencoded),
            # use cgi.FieldStorage which knows how to parse without us consuming stdin.
            try:
                form = cgi.FieldStorage()
                for key in form.keys():
                    # FieldStorage.getvalue returns string or list; normalize to str
                    post[key] = form.getvalue(key)
                debug("Parsed form fields:", post)
            except Exception as e:
                debug("FieldStorage error:", e)
                post = {}
    return {
        'method': method,
        'query': query,
        'headers': headers,
        'post': post,
        'raw_json': raw_json
    }

# Main handler
def main():
    try:
        req = read_request()
        query = req['query']
        post = req['post']
        headers = req['headers']

        # Determine action: prefer query string 'action', else post 'action'
        action = ''
        if query.get('action'):
            action = query.get('action', [''])[0]
        elif post.get('action'):
            action = post.get('action')

        action = action or ''

        if not action:
            json_print({'success': False, 'error': 'No action specified'})
            return

        # Extract token: prefer query param, then POST field, then Authorization header (Bearer)
        token = ''
        if query.get('token'):
            token = query.get('token', [''])[0]
        elif post.get('token'):
            token = post.get('token')
        else:
            auth_header = headers.get('Authorization') or headers.get('Auth') or ''
            if auth_header.lower().startswith('bearer '):
                token = auth_header.split(None, 1)[1].strip()

        debug("Resolved token:", bool(token))

        user_id = authenticate_token(token)
        if not user_id:
            json_print({'success': False, 'error': 'Invalid or expired token'})
            return

        # ACTION: create
        if action == 'create':
            # title required
            title = (post.get('title') or '').strip()
            description = post.get('description') or None
            status = post.get('status') or 'Pending'
            priority = post.get('priority') or 'medium'
            due_date = post.get('due_date') or None

            debug("Creating task:", title, status, due_date)

            if not title:
                json_print({'success': False, 'error': 'Title is required'})
                return

            conn = db_connect()
            if not conn:
                json_print({'success': False, 'error': 'Database connection failed'})
                return

            try:
                cursor = conn.cursor()
                if due_date:
                    cursor.execute("""
                        INSERT INTO tasks (user_id, title, description, status, priority, due_date, created_at)
                        VALUES (%s, %s, %s, %s, %s, %s, NOW())
                    """, (user_id, title, description, status, priority, due_date))
                else:
                    cursor.execute("""
                        INSERT INTO tasks (user_id, title, description, status, priority, created_at)
                        VALUES (%s, %s, %s, %s, %s, NOW())
                    """, (user_id, title, description, status, priority))

                task_id = cursor.lastrowid
                cursor.close()
                conn.close()

                json_print({'success': True, 'message': 'Task created successfully', 'task_id': task_id})
                return
            except Exception as e:
                debug("Insert error:", e)
                try:
                    conn.close()
                except:
                    pass
                json_print({'success': False, 'error': 'Database error: ' + str(e)})
                return

        # ACTION: list
        elif action == 'list':
            conn = db_connect()
            if not conn:
                json_print({'success': False, 'error': 'Database connection failed'})
                return
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, title, description, status, priority,
                           DATE_FORMAT(created_at, '%%Y-%%m-%%d %%H:%%i:%%s') as created_at,
                           DATE_FORMAT(due_date, '%%Y-%%m-%%d') as due_date,
                           reminder_sent
                    FROM tasks 
                    WHERE user_id = %s 
                    ORDER BY created_at DESC
                """, (user_id,))
                tasks = cursor.fetchall()
                cursor.close()
                conn.close()
                json_print({'success': True, 'data': {'tasks': tasks, 'count': len(tasks)}})
                return
            except Exception as e:
                debug("List error:", e)
                try:
                    conn.close()
                except:
                    pass
                json_print({'success': False, 'error': str(e)})
                return

        # ACTION: delete
        elif action == 'delete':
            # Accept id from query or post
            task_id = ''
            if query.get('id'):
                task_id = query.get('id', [''])[0]
            elif post.get('id'):
                task_id = post.get('id')

            if not task_id:
                json_print({'success': False, 'error': 'Task ID is required'})
                return

            conn = db_connect()
            if not conn:
                json_print({'success': False, 'error': 'Database connection failed'})
                return

            try:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM tasks WHERE id = %s AND user_id = %s", (task_id, user_id))
                affected = cursor.rowcount
                cursor.close()
                conn.close()
                if affected > 0:
                    json_print({'success': True, 'message': 'Task deleted successfully'})
                else:
                    json_print({'success': False, 'error': 'Task not found or access denied'})
                return
            except Exception as e:
                debug("Delete error:", e)
                try:
                    conn.close()
                except:
                    pass
                json_print({'success': False, 'error': str(e)})
                return

        else:
            json_print({'success': False, 'error': 'Invalid action'})
            return

    except Exception as e:
        debug("General error:", e)
        json_print({'success': False, 'error': 'Server error: ' + str(e)})


if __name__ == '__main__':
    main()
