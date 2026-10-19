HTML_TEMPLATE_SURVEY = '''
<form action='/survey' method='POST'>
  <p>Last night was:</p>
  <select name="temp">
    <option value="f">Cold</option>
    <option value="o">Ok</option>
    <option value="c">Warm</option>
  </select>
  <br />
  <p>Who are you?</p>
  <select name="user">
    {user_options}
  </select>
  <button type="submit">Submit</button>
</form>
'''

HTML_TEMPLATE_OK = '''
<p>Your response was saved correctly.</p>

<script>setTimeout(() => {window.location.href = "/"}, 1000)</script>
'''

HTML_TEMPLATE_REGISTER = '''
<form action='/register' method='POST'>
  <p>Your name:</p>
  <input name="name" type="text" />
  <br />
  <p>Your LINE Id</p>
  <input name="line" type="text" required/>
  <button type="submit">Submit</button>
</form>
'''

HTML_TEMPLATE_ASSIGN_DEVICE = '''
<form action='/assign' method='POST'>
  <p>Device (Only unassigned)</p>
  <select name="dev">
    {device_options}
  </select>
  <br />
  <p>User</p>
  <select name="user">
    {user_options}
  </select>
  <button type="submit">Submit</button>
</form>
'''
from functools import cached_property
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qsl, urlparse
import os
import sqlite3
import uuid
from datetime import datetime

DB_FILE = os.environ.get("SMARTECO_DATABASE_LOCATION", "database.db")

def get_user_options():
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, name FROM users")
            users = cursor.fetchall()
            
        if not users:
            return '<option disabled>No users registered yet</option>'
            
        return "".join([f'<option value="{u[0]}">{u[1]}</option>\n' for u in users])
    except Exception as e:
        print(f"[DB GET ERROR] users: {e}")
        return '<option disabled>Error loading users</option>'

def get_unassigned_device_options():
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT mac, hostname FROM devices WHERE owner_id IS NULL OR owner_id = ''")
            devices = cursor.fetchall()
            
        if not devices:
            return '<option disabled>No unassigned devices found</option>'
            
        return "".join([f'<option value="{d[0]}">{d[1]} ({d[0]})</option>\n' for d in devices])
    except Exception as e:
        print(f"[DB GET ERROR] devices: {e}")
        return '<option disabled>Error loading devices</option>'


def handle_db_operation(action, data):
    print(f"[DB LOG] {action} | {data}")
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            
            if action == "save_survey":
                user_id = data.get("user")
                temp = data.get("temp")
                
                was_cold = 1 if temp == 'f' else 0
                was_ok = 1 if temp == 'o' else 0
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                cursor.execute(
                    "INSERT INTO surveys (user_id, date, was_cold, was_ok) VALUES (?, ?, ?, ?)",
                    (user_id, now, was_cold, was_ok)
                )
                
            elif action == "register_user":
                new_id = uuid.uuid4().hex
                name = data.get("name")
                line_id = data.get("line")
                
                cursor.execute(
                    "INSERT INTO users (id, name, line_id) VALUES (?, ?, ?)",
                    (new_id, name, line_id)
                )
                
            elif action == "assign_device":
                mac = data.get("dev")
                user_id = data.get("user")
                
                cursor.execute(
                    "UPDATE devices SET owner_id = ? WHERE mac = ?",
                    (user_id, mac)
                )
            
            conn.commit()
    except Exception as e:
        print(f"[DB POST ERROR] There was an error processing {action}: {e}")

class WebRequestHandler(BaseHTTPRequestHandler):
    @cached_property
    def url(self):
        return urlparse(self.path)

    @cached_property
    def query_data(self):
        return dict(parse_qsl(self.url.query))

    @cached_property
    def post_data(self):
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length == 0:
            return b""
        return self.rfile.read(content_length)

    @cached_property
    def form_data(self):
        return dict(parse_qsl(self.post_data.decode("utf-8")))

    @cached_property
    def cookies(self):
        return SimpleCookie(self.headers.get("Cookie"))

    def send_html(self, content):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(content.encode("utf-8"))

    def do_GET(self):
        path = self.url.path
        
        if path == "/survey":
            html = HTML_TEMPLATE_SURVEY.format(user_options=get_user_options())
            self.send_html(html)
        elif path == "/register":
            self.send_html(HTML_TEMPLATE_REGISTER)
        elif path == "/assign":
            html = HTML_TEMPLATE_ASSIGN_DEVICE.format(
                device_options=get_unassigned_device_options(),
                user_options=get_user_options()
            )
            self.send_html(html)
        elif path == "/":
            self.send_html("<h1>Menu</h1><a href='/survey'>Survey</a><br><a href='/register'>Register</a><br><a href='/assign'>Assign</a>")
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"404 Not Found")

    def do_POST(self):
        path = self.url.path
        
        if path == "/survey":
            handle_db_operation("save_survey", self.form_data)
            self.send_html(HTML_TEMPLATE_OK)
            
        elif path == "/register":
            handle_db_operation("register_user", self.form_data)
            self.send_html(HTML_TEMPLATE_OK)
            
        elif path == "/assign":
            handle_db_operation("assign_device", self.form_data)
            self.send_html(HTML_TEMPLATE_OK)
            
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"404 Not Found")

if __name__ == "__main__":
    host = os.environ.get("SMARTECO_HTTP_HOST", "0.0.0.0")
    port = int(os.environ.get("SMARTECO_HTTP_PORT", 8080))
    print(f"Trying to allocate on {host}:{port}")
    HTTPServer.allow_reuse_address = True
    server = HTTPServer((host, port), WebRequestHandler)
    print(f"Server running on http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nClosing server...")
        server.server_close()