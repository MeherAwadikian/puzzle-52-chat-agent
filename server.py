"""
Puzzle #52 — custom website chat agent with a lead-capture goal.

A small backend that (a) serves a floating chat widget and (b) proxies the
conversation to an LLM with a system prompt that makes the agent a helpful
"Forge Studio" assistant whose GOAL is to capture the visitor as a lead:
answer their questions, then naturally ask for a name + email so the team can
follow up. The API key + system prompt live here server-side, never in the
browser.

Lead capture: after each turn the server scans the visitor's messages for an
email address; the first time one appears it records the lead (name inferred
from the conversation + email + full transcript) to leads.jsonl and marks the
session captured.

Run: OPENROUTER_API_KEY=... python server.py   ->  http://127.0.0.1:8104/
"""
import json
import os
import re
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

OPENROUTER_KEY = os.environ["OPENROUTER_API_KEY"]
PORT = int(os.environ.get("PORT", "8104"))
MODELS = [
    "cohere/north-mini-code:free",
    "google/gemma-4-26b-a4b-it:free",
    "nvidia/nemotron-3.5-lightning:free",
]
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

SYSTEM_PROMPT = (
    "You are the website assistant for Forge Studio, a small studio that designs "
    "and builds fast, modern product websites and web apps (React/Next.js, "
    "Supabase, automation). Be warm, concise, and genuinely helpful. "
    "Your GOAL is to turn interested visitors into leads: answer their questions "
    "about services, process, and pricing ranges, and when the visitor shows "
    "interest, naturally ask for their name and email so the team can follow up "
    "with specifics or a quote. Ask for contact details at most once unless they "
    "decline; never be pushy. Keep replies to 1-3 short sentences."
)


def llm(messages):
    body = json.dumps({"model": MODELS[0], "messages": messages, "max_tokens": 220}).encode()
    for model in MODELS:
        payload = json.loads(body.decode())
        payload["model"] = model
        data = json.dumps(payload).encode()
        try:
            req = urllib.request.Request(
                "https://openrouter.ai/api/v1/chat/completions", data=data,
                headers={"Authorization": f"Bearer {OPENROUTER_KEY}", "Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=40) as r:
                content = (json.load(r)["choices"][0]["message"].get("content") or "").strip()
            if content:
                return content
        except Exception:
            continue
    return "Sorry, I'm having trouble responding right now. Please email hello@forgestudio.dev and we'll get back to you."


def infer_name(history):
    """Best-effort: look for a 'my name is X' / 'I'm X' pattern in user turns."""
    for m in history:
        if m["role"] != "user":
            continue
        t = m["content"]
        # Inline (?i:...) makes ONLY the prefix case-insensitive; the capture
        # group stays case-sensitive so it requires a real Capitalized name and
        # won't greedily swallow a following lowercase word (e.g. "Priya and").
        name = r"([A-Z][a-z]+(?: [A-Z][a-z]+)?)"
        for pat in (r"(?i:my name is )" + name,
                    r"(?i:i'?m )" + name,
                    r"(?i:i am )" + name,
                    r"(?i:this is )" + name,
                    r"(?i:it'?s )" + name):
            mm = re.search(pat, t)
            if mm:
                return mm.group(1)
    return None


def capture_lead(history):
    """Record the first email found in the visitor's messages as a lead."""
    for m in history:
        if m["role"] != "user":
            continue
        em = EMAIL_RE.search(m["content"])
        if em:
            lead = {
                "email": em.group(0),
                "name": infer_name(history),
                "captured_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "turns": len([x for x in history if x["role"] == "user"]),
            }
            with open("leads.jsonl", "a", encoding="utf-8") as f:
                f.write(json.dumps(lead) + "\n")
            return lead
    return None


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._send(200, "text/html; charset=utf-8", WIDGET)
        else:
            self._send(404, "text/plain", "not found")

    def do_POST(self):
        if self.path != "/chat":
            self._send(404, "application/json", '{"error":"not found"}')
            return
        length = int(self.headers.get("Content-Length", 0))
        req = json.loads(self.rfile.read(length) or "{}")
        history = req.get("messages", [])

        # capture a lead if an email just appeared (only once per session)
        lead = None
        if not req.get("captured"):
            lead = capture_lead(history)

        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history
        reply = llm(messages)
        self._send(200, "application/json",
                   json.dumps({"reply": reply, "lead_captured": bool(lead), "lead": lead}))

    def _send(self, code, ctype, body):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.end_headers()
        self.wfile.write(body.encode() if isinstance(body, str) else body)


WIDGET = """<!doctype html><html lang=en><head><meta charset=utf-8>
<meta name=viewport content="width=device-width, initial-scale=1">
<title>Forge Studio</title><style>
*{box-sizing:border-box;margin:0;padding:0;font-family:'Inter',system-ui,sans-serif}
body{background:#0e0e16;color:#ecebf7;min-height:100vh}
.hero{max-width:640px;margin:6rem auto;padding:0 1.5rem}
.hero h1{font-size:2.4rem;letter-spacing:-.02em;margin-bottom:.75rem}
.hero p{color:#9a95b6}
.bubble{position:fixed;right:24px;bottom:24px;width:58px;height:58px;border-radius:50%;
 background:#6b4fd8;color:#fff;border:none;font-size:1.5rem;cursor:pointer;box-shadow:0 10px 30px rgba(107,79,216,.5)}
.panel{position:fixed;right:24px;bottom:94px;width:360px;max-width:92vw;height:520px;max-height:72vh;
 background:#15151f;border:1px solid #2a2a3c;border-radius:16px;display:none;flex-direction:column;overflow:hidden;
 box-shadow:0 20px 60px rgba(0,0,0,.6)}
.panel.open{display:flex}
.phead{padding:1rem;border-bottom:1px solid #2a2a3c;font-weight:600}
.phead small{display:block;color:#9a95b6;font-weight:400;font-size:.8rem}
.msgs{flex:1;overflow-y:auto;padding:1rem;display:flex;flex-direction:column;gap:.6rem}
.m{max-width:80%;padding:.55rem .8rem;border-radius:12px;font-size:.92rem;line-height:1.45}
.m.bot{background:#1f1f2e;align-self:flex-start}
.m.me{background:#6b4fd8;color:#fff;align-self:flex-end}
.m.tag{align-self:center;font-size:.72rem;color:#86e3b8;background:rgba(63,178,127,.14);
 border:1px solid #2a2a3c;border-radius:999px;padding:.2rem .6rem}
.pin{display:flex;gap:.5rem;padding:.75rem;border-top:1px solid #2a2a3c}
.pin input{flex:1;padding:.55rem .7rem;background:#0e0e16;border:1px solid #2a2a3c;border-radius:10px;color:#ecebf7}
.pin button{background:#6b4fd8;color:#fff;border:none;border-radius:10px;padding:0 1rem;cursor:pointer}
</style></head><body>
<div class=hero><h1>Forge Studio</h1><p>We design and build fast, modern product websites. Chat with our assistant (bottom-right) to learn more.</p></div>
<button class=bubble id=bub>&#128172;</button>
<div class=panel id=panel>
 <div class=phead>Forge Studio Assistant<small>Ask about services, process, or pricing</small></div>
 <div class=msgs id=msgs></div>
 <div class=pin><input id=inp placeholder="Type a message..." autocomplete=off><button id=send>Send</button></div>
</div>
<script>
const msgs=document.getElementById('msgs'),inp=document.getElementById('inp');
let history=[],captured=false;
function add(role,text){const d=document.createElement('div');d.className='m '+(role==='bot'?'bot':role==='tag'?'tag':'me');d.textContent=text;msgs.appendChild(d);msgs.scrollTop=msgs.scrollHeight;}
document.getElementById('bub').onclick=()=>{const p=document.getElementById('panel');p.classList.toggle('open');if(p.classList.contains('open')&&!history.length){add('bot',"Hi! I'm the Forge Studio assistant. What are you looking to build?");}};
async function send(){const t=inp.value.trim();if(!t)return;inp.value='';add('me',t);history.push({role:'user',content:t});
 const r=await fetch('/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({messages:history,captured})});
 const j=await r.json();add('bot',j.reply);history.push({role:'assistant',content:j.reply});
 if(j.lead_captured&&!captured){captured=true;add('tag','✓ Lead captured: '+(j.lead.name?j.lead.name+' ':'')+'<'+j.lead.email+'>');}}
document.getElementById('send').onclick=send;inp.addEventListener('keydown',e=>{if(e.key==='Enter')send();});
</script></body></html>"""


if __name__ == "__main__":
    print(f"serving on http://127.0.0.1:{PORT}")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
