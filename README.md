# Puzzle #52 — custom website chat agent (LLM API, lead-capture goal)

Brief (Task Forge puzzle tracker): custom chat agent for website (LLM API, lead capture goal) — none/generic (LLM API).

A floating website chat widget backed by an LLM, whose **goal is to turn
visitors into leads**: it answers questions about the business, and when a
visitor shows interest it naturally asks for a name + email, then records the
lead.

## How it works

- **`server.py`** serves the widget and exposes `POST /chat`. The LLM API key
  and the system prompt live server-side (never shipped to the browser). The
  system prompt makes the agent a concise, helpful "Forge Studio" assistant
  whose explicit goal is lead capture (answer, then ask for contact details
  when interest is shown, at most once, never pushy).
- **Lead capture**: after each turn the server scans the visitor's messages for
  an email; the first time one appears it records the lead (email + a name
  inferred from the conversation + turn count) to `leads.jsonl` and tells the
  widget, which shows a "✓ Lead captured" tag.
- **Model resilience**: tries a list of free OpenRouter models in order and
  falls back to a polite "email us" message if all fail (free models
  rate-limit), so the widget never shows a hard error.

## Verified live (real LLM, real capture)

Driven through the actual widget UI in a browser (claude-in-chrome):

```
visitor: Do you build dashboards with charts?
agent:   Yes—we build interactive dashboards with charts using React/Next.js
         and Supabase. Would you like to discuss a project?
visitor: Perfect. My name is Sam Rivera, email sam@dataco.io
agent:   Thanks, Sam! The team will be in touch soon.
         ✓ Lead captured: Sam Rivera <sam@dataco.io>
```

The agent answered on-brand AND drove toward contact capture; the lead was
recorded with the correct name + email. Name extraction was unit-tested across
"My name is X", "I'm X", "I am X", "this is X Y" (two-word), and the
no-name-stated case (→ null).

### Two real bugs caught by verification (and fixed)
1. **Name regex too case-sensitive, then too greedy.** First version missed
   capitalized prefixes ("My name is"); the naive `re.IGNORECASE` fix then made
   the *name* group case-insensitive too, so it grabbed trailing lowercase words
   ("Priya and"). Fixed with inline `(?i:prefix)` so only the prefix is
   case-insensitive and the name stays genuinely Capitalized.
2. **Stale server process.** On Windows, `pkill -f server.py` did not actually
   kill the old server, so the browser kept hitting a zombie running the old
   code — the fix looked broken until the real PID (via `Get-NetTCPConnection`)
   was killed. Lesson: kill by port/PID on Windows, not `pkill`.

## Run
```
OPENROUTER_API_KEY=... python server.py   # http://127.0.0.1:8104/
```
Embed the widget on any site and point its `/chat` fetch at this backend.
