#!/usr/bin/python3
"""
Telex Device - Internal web chat bridge
"""
__author__      = "Andrew Sozonnyk"
__email__       = ""
__copyright__   = "Copyright 2026"
__license__     = "GPL3"
__version__     = "0.0.1"

import html
import json
import logging
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import txBase
import txCode

l = logging.getLogger("piTelex." + __name__)

RING_COMMAND = '\x1b.RING'


PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
:root {
  color-scheme: light dark;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  --bg: #f4f1e8;
  --panel: #fffdf6;
  --ink: #1f2320;
  --muted: #6c6a61;
  --line: #d6d0bf;
  --web: #114b5f;
  --tty: #6f3d00;
  --system: #4d5560;
}

* {
  box-sizing: border-box;
}

body {
  margin: 0;
  min-height: 100vh;
  background: var(--bg);
  color: var(--ink);
}

.app {
  display: grid;
  grid-template-rows: auto 1fr auto;
  min-height: 100vh;
  max-width: 980px;
  margin: 0 auto;
  padding: 16px;
  gap: 12px;
}

.topbar,
.composer {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.title {
  flex: 1 1 auto;
  min-width: 220px;
}

h1 {
  margin: 0;
  font-size: 22px;
  font-weight: 700;
}

.status {
  margin-top: 3px;
  color: var(--muted);
  font-size: 13px;
}

button {
  min-height: 38px;
  border: 1px solid var(--line);
  background: var(--panel);
  color: var(--ink);
  padding: 0 12px;
  border-radius: 6px;
  font: inherit;
  cursor: pointer;
}

button.primary {
  background: var(--web);
  border-color: var(--web);
  color: white;
}

button:disabled {
  cursor: default;
  opacity: 0.55;
}

button.attach {
  width: 42px;
  min-width: 42px;
  padding: 0;
  font-size: 20px;
  line-height: 1;
}

.file-input {
  display: none;
}

.chat {
  overflow: auto;
  border: 1px solid var(--line);
  background: var(--panel);
  border-radius: 6px;
  padding: 12px;
}

.message {
  max-width: 82%;
  margin: 0 0 10px;
  padding: 8px 10px;
  border-radius: 6px;
  border: 1px solid var(--line);
  background: #ffffff;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.message.web {
  margin-left: auto;
  border-color: #8cb6c4;
}

.message.tty {
  margin-right: auto;
  border-color: #d2ad75;
}

.message.system {
  max-width: 100%;
  margin-left: auto;
  margin-right: auto;
  color: var(--system);
  background: transparent;
  border-style: dashed;
  text-align: center;
}

.meta {
  display: block;
  margin-bottom: 4px;
  color: var(--muted);
  font-size: 12px;
}

textarea {
  flex: 1 1 320px;
  min-height: 42px;
  max-height: 140px;
  resize: vertical;
  border: 1px solid var(--line);
  border-radius: 6px;
  background: var(--panel);
  color: var(--ink);
  padding: 10px;
  font: inherit;
}

@media (prefers-color-scheme: dark) {
  :root {
    --bg: #181914;
    --panel: #23241e;
    --ink: #f2eee2;
    --muted: #aaa390;
    --line: #484535;
    --web: #2f7890;
    --tty: #b9853d;
    --system: #b5b8bd;
  }

  .message {
    background: #20211c;
  }
}
</style>
</head>
<body>
<main class="app">
  <header class="topbar">
    <div class="title">
      <h1>__TITLE__</h1>
      <div id="status" class="status">Disconnected</div>
    </div>
    <button id="start" class="primary" type="button">Start Chat</button>
    <button id="ring" type="button">Ring Phone</button>
    <button id="end" type="button">End</button>
  </header>
  <section id="chat" class="chat" aria-live="polite"></section>
  <form id="form" class="composer">
    <textarea id="text" maxlength="800" placeholder="Message"></textarea>
    <input id="file" class="file-input" type="file" accept=".txt,text/plain">
    <button id="attach" class="attach" type="button" title="Attach text file" aria-label="Attach text file">+</button>
    <button class="primary" type="submit">Send</button>
  </form>
</main>
<script>
let lastId = 0;
let active = false;

const chat = document.getElementById("chat");
const statusLine = document.getElementById("status");
const form = document.getElementById("form");
const text = document.getElementById("text");
const fileInput = document.getElementById("file");
const attachButton = document.getElementById("attach");
const startButton = document.getElementById("start");
const ringButton = document.getElementById("ring");
const endButton = document.getElementById("end");

function escapeText(value) {
  return value.replace(/[&<>"']/g, (ch) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;"
  }[ch]));
}

function updateState(nextActive, incoming) {
  active = nextActive;
  statusLine.textContent = active ? "Chat active" : "Disconnected";
  startButton.disabled = active;
  endButton.disabled = !active;
  if (incoming) {
    statusLine.textContent += " - receiving: " + incoming;
  }
}

function addMessage(event) {
  const item = document.createElement("article");
  item.className = "message " + event.kind;
  const label = event.kind === "web" ? "Web" : event.kind === "tty" ? "Teletype" : "System";
  item.innerHTML = `<span class="meta">${event.time} ${label}</span>${escapeText(event.text)}`;
  chat.appendChild(item);
  chat.scrollTop = chat.scrollHeight;
}

async function api(path, body) {
  const response = await fetch(path, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(body || {})
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json();
}

async function poll() {
  try {
    const response = await fetch("/api/events?since=" + lastId, {cache: "no-store"});
    const data = await response.json();
    for (const event of data.events) {
      lastId = Math.max(lastId, event.id);
      addMessage(event);
    }
    updateState(data.active, data.incoming);
  } catch (err) {
    statusLine.textContent = "Connection lost";
  }
}

startButton.addEventListener("click", async () => {
  await api("/api/start");
  await poll();
  text.focus();
});

ringButton.addEventListener("click", async () => {
  await api("/api/ring");
  await poll();
});

endButton.addEventListener("click", async () => {
  await api("/api/end");
  await poll();
});

attachButton.addEventListener("click", () => {
  fileInput.click();
});

fileInput.addEventListener("change", async () => {
  const file = fileInput.files[0];
  fileInput.value = "";
  if (!file) {
    return;
  }
  if (!file.name.toLowerCase().endsWith(".txt")) {
    statusLine.textContent = "Only .txt files are accepted";
    return;
  }

  try {
    await api("/api/send-file", {
      filename: file.name,
      text: await file.text()
    });
    await poll();
  } catch (err) {
    statusLine.textContent = "Upload failed: " + err.message;
  }
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = text.value.trim();
  if (!message) {
    return;
  }
  text.value = "";
  await api("/api/send", {text: message});
  await poll();
});

text.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    form.requestSubmit();
  }
});

setInterval(poll, 1000);
poll();
</script>
</body>
</html>
"""


class ReusableThreadingHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True


class TelexWeb(txBase.TelexBase):
    def __init__(self, **params):
        super().__init__()

        self.id = 'Web'
        self.params = params

        self._host = params.get('host', '0.0.0.0')
        self._port = int(params.get('port', 8080))
        self._title = params.get('title', 'piTelex Chat')
        self._input_sources = set(params.get('input_sources', ['piT', 'Trm', 'Scn']))
        self._line_width = int(params.get('line_width', 69))
        self._max_history = int(params.get('max_history', 200))
        self._max_message_chars = int(params.get('max_message_chars', 800))
        self._max_file_chars = int(params.get('max_file_chars', 20000))
        self._max_request_bytes = int(params.get('max_request_bytes', self._max_file_chars * 4 + 4096))
        self._ring_command = params.get('ring_command', RING_COMMAND)
        self._teletype_end_sources = set(params.get('teletype_end_sources', ['piC']))

        self._rx_buffer = []
        self._incoming = ''
        self._events = []
        self._next_event_id = 1
        self._active = False
        self._lock = threading.RLock()

        self._server = ReusableThreadingHTTPServer((self._host, self._port), self._make_handler())
        self._thread = threading.Thread(target=self._server.serve_forever, name='WebChat', daemon=True)
        self._thread.start()

        host, port = self._server.server_address
        l.info("web chat listening on {}:{}".format(host, port))

    def exit(self):
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=2)

    # =====

    def read(self) -> str:
        with self._lock:
            if self._rx_buffer:
                return self._rx_buffer.pop(0)

    # -----

    def write(self, a:str, source:str):
        if not a:
            return

        with self._lock:
            if len(a) != 1:
                if a in ('\x1bST', '\x1bZ', '\x1bZZ'):
                    self._finish_chat_locked('Chat ended')
                elif a == '\x1bWB':
                    self._finish_chat_locked('Chat ended')
                return

            if self._active and source in self._input_sources:
                self._record_teletype_char_locked(a)

    # -----

    def observe(self, a:str, source:str):
        if len(a) <= 1 or a[0] != '\x1b':
            return
        if source not in self._teletype_end_sources:
            return
        if a[1:] not in ('ST', 'Z', 'ZZ', 'WB'):
            return

        with self._lock:
            self._finish_chat_locked('Chat ended by teletype')

    # =====

    def start_chat(self):
        with self._lock:
            if not self._active:
                self._rx_buffer.append(self._ring_command)
                self._rx_buffer.append('\x1bA')
                self._active = True
                self._add_event_locked('system', 'Chat started')
            else:
                self._rx_buffer.append(self._ring_command)
                self._add_event_locked('system', 'Phone ring requested')

    # -----

    def ring_phone(self):
        with self._lock:
            self._rx_buffer.append(self._ring_command)
            self._add_event_locked('system', 'Phone ring requested')

    # -----

    def end_chat(self):
        with self._lock:
            self._finish_incoming_locked()
            if self._active:
                self._rx_buffer.append('\x1bST')
            self._finish_chat_locked('Chat ended', clear_output=False)

    # -----

    def send_web_message(self, text):
        text = self._clean_message(text)
        if not text:
            return
        if len(text) > self._max_message_chars:
            raise ValueError("message is too long")

        with self._lock:
            if not self._active:
                self._rx_buffer.append(self._ring_command)
                self._rx_buffer.append('\x1bA')
                self._active = True
                self._add_event_locked('system', 'Chat started')

            self._add_event_locked('web', text)
            for a in self._format_for_teletype(text):
                self._rx_buffer.append(a)

    # -----

    def send_text_file(self, filename, text):
        filename = self._clean_filename(filename)
        if not filename.lower().endswith('.txt'):
            raise ValueError("only .txt files are accepted")
        text = self._clean_file_text(text)
        if len(text) > self._max_file_chars:
            raise ValueError("file is too large")

        with self._lock:
            if not self._active:
                self._rx_buffer.append(self._ring_command)
                self._rx_buffer.append('\x1bA')
                self._active = True
                self._add_event_locked('system', 'Chat started')

            self._add_event_locked('web', 'Attached file: {}'.format(filename))
            self._rx_buffer.extend(self._format_file_for_teletype(filename, text))

    # -----

    def get_events(self, since):
        with self._lock:
            events = [event.copy() for event in self._events if event['id'] > since]
            return {
                'active': self._active,
                'incoming': self._incoming,
                'events': events,
            }

    # =====

    def _make_handler(self):
        device = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                parsed = urlparse(self.path)
                if parsed.path == '/':
                    self._send_html(device._render_page())
                elif parsed.path == '/api/events':
                    query = parse_qs(parsed.query)
                    try:
                        since = int(query.get('since', ['0'])[0])
                    except (TypeError, ValueError):
                        since = 0
                    self._send_json(device.get_events(since))
                else:
                    self._send_text(404, 'not found')

            def do_POST(self):
                parsed = urlparse(self.path)
                try:
                    if parsed.path == '/api/start':
                        device.start_chat()
                        self._send_json({'ok': True})
                    elif parsed.path == '/api/ring':
                        device.ring_phone()
                        self._send_json({'ok': True})
                    elif parsed.path == '/api/end':
                        device.end_chat()
                        self._send_json({'ok': True})
                    elif parsed.path == '/api/send':
                        data = self._read_json()
                        device.send_web_message(data.get('text', ''))
                        self._send_json({'ok': True})
                    elif parsed.path == '/api/send-file':
                        data = self._read_json()
                        device.send_text_file(data.get('filename', ''), data.get('text', ''))
                        self._send_json({'ok': True})
                    else:
                        self._send_text(404, 'not found')
                except ValueError as e:
                    self._send_text(400, str(e))

            def log_message(self, fmt, *args):
                l.debug("web chat: " + fmt, *args)

            def _read_json(self):
                try:
                    length = int(self.headers.get('Content-Length', '0'))
                except ValueError:
                    length = 0
                if length > device._max_request_bytes:
                    raise ValueError("request is too large")
                raw = self.rfile.read(length)
                if not raw:
                    return {}
                return json.loads(raw.decode('utf-8'))

            def _send_html(self, text):
                self._send_bytes(200, 'text/html; charset=utf-8', text.encode('utf-8'))

            def _send_json(self, data):
                body = json.dumps(data).encode('utf-8')
                self._send_bytes(200, 'application/json; charset=utf-8', body)

            def _send_text(self, status, text):
                self._send_bytes(status, 'text/plain; charset=utf-8', text.encode('utf-8'))

            def _send_bytes(self, status, content_type, body):
                self.send_response(status)
                self.send_header('Content-Type', content_type)
                self.send_header('Content-Length', str(len(body)))
                self.send_header('Cache-Control', 'no-store')
                self.end_headers()
                self.wfile.write(body)

        return Handler

    # -----

    def _render_page(self):
        title = html.escape(self._title)
        return PAGE.replace('__TITLE__', title)

    # -----

    def _add_event_locked(self, kind, text):
        self._events.append({
            'id': self._next_event_id,
            'kind': kind,
            'text': text,
            'time': time.strftime('%H:%M:%S', time.localtime()),
        })
        self._next_event_id += 1
        if len(self._events) > self._max_history:
            del self._events[:len(self._events) - self._max_history]

    # -----

    def _clean_message(self, text):
        if text is None:
            return ''
        text = str(text)
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        lines = [line.strip() for line in text.split('\n')]
        return '\n'.join(line for line in lines if line).strip()

    # -----

    def _clean_filename(self, filename):
        filename = str(filename or '').strip()
        filename = filename.replace('\\', '/').split('/')[-1]
        return filename[:120]

    # -----

    def _clean_file_text(self, text):
        if text is None:
            return ''
        return str(text)

    # -----

    def _format_for_teletype(self, text):
        lines = []
        raw_lines = text.split('\n')
        for nr, raw in enumerate(raw_lines):
            prefix = 'WEB: ' if nr == 0 else '     '
            lines.extend(self._wrap_line(prefix + raw))
        return '\r\n' + '\r\n'.join(lines) + '\r\n'

    # -----

    def _format_file_for_teletype(self, filename, text):
        filename = txCode.BaudotMurrayCode.translate(filename).strip()
        text = self._normalize_file_line_endings(text)
        header = 'ATTACHMENT START: {}'.format(filename)
        footer = 'ATTACHMENT END: {}'.format(filename)

        if text and not text.endswith('\r\n'):
            text += '\r\n'

        return '\r\n\r\n' + header + '\r\n' + text + footer + '\r\n'

    # -----

    def _normalize_file_line_endings(self, text):
        return text.replace('\r\n', '\n').replace('\r', '\n').replace('\n', '\r\n')

    # -----

    def _wrap_line(self, line):
        wrapped = []
        line = txCode.BaudotMurrayCode.translate(line).strip()

        while len(line) > self._line_width:
            split_at = line.rfind(' ', 0, self._line_width + 1)
            if split_at <= 0:
                split_at = self._line_width
            wrapped.append(line[:split_at].strip())
            line = line[split_at:].strip()

        if line:
            wrapped.append(line)
        return wrapped

    # -----

    def _record_teletype_char_locked(self, a):
        if a in ('<', '>', '\xb0'):
            return
        if a in ('\r', '\n'):
            self._finish_incoming_locked()
            return
        if a in ('\b', '\x08'):
            self._incoming = self._incoming[:-1]
            return

        self._incoming += a
        if len(self._incoming) >= self._max_message_chars:
            self._finish_incoming_locked()

    # -----

    def _finish_incoming_locked(self):
        text = self._incoming.strip()
        self._incoming = ''
        if text:
            self._add_event_locked('tty', text)

    # -----

    def _finish_chat_locked(self, event_text, clear_output=True):
        was_active = self._active
        if clear_output:
            self._rx_buffer.clear()
        self._finish_incoming_locked()
        self._active = False
        if was_active:
            self._add_event_locked('system', event_text)


#######
