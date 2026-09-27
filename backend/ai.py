import os
import re
import json
import requests
from datetime import datetime

try:
    from openai import OpenAI
except Exception:
    OpenAI = None

# ---------------------------------------------------------------------------
# Multi-provider AI backend.
#
# AI_PROVIDER=auto (default)  -> tries Anthropic, then OpenAI, then a local
#                                 Ollama server, then falls back to a
#                                 rule-based responder that still works with
#                                 zero setup.
# AI_PROVIDER=anthropic|openai|ollama|off  -> force one, or disable real AI.
#
# Only ONE of these needs to be configured for real AI to kick in:
#   ANTHROPIC_API_KEY   (https://console.anthropic.com)
#   OPENAI_API_KEY      (https://platform.openai.com)
#   Ollama running locally (https://ollama.com -- `ollama pull llama3.2`,
#   no key needed, fully free, fully local).
# ---------------------------------------------------------------------------

PROVIDER = os.getenv("AI_PROVIDER", "auto").lower()

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")


def _call_openai(instructions, prompt, want_json=False):
    key = os.getenv("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")
    if not key or OpenAI is None:
        return None
    try:
        client = OpenAI(api_key=key)
        kwargs = {}
        if want_json:
            kwargs["response_format"] = {"type": "json_object"}
        resp = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "system", "content": instructions}, {"role": "user", "content": prompt}],
            max_tokens=700,
            temperature=0.4,
            **kwargs,
        )
        return resp.choices[0].message.content.strip()
    except Exception:
        return None


def _call_anthropic(instructions, prompt):
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        return None
    try:
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": ANTHROPIC_MODEL,
                "max_tokens": 700,
                "system": instructions,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()
        return "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text").strip()
    except Exception:
        return None


def _call_ollama(instructions, prompt):
    try:
        resp = requests.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": OLLAMA_MODEL,
                "stream": False,
                "messages": [{"role": "system", "content": instructions}, {"role": "user", "content": prompt}],
            },
            timeout=25,
        )
        resp.raise_for_status()
        return resp.json().get("message", {}).get("content", "").strip() or None
    except Exception:
        return None


def _call_ai(instructions, prompt, want_json=False):
    """Try providers in order until one answers. Returns None if none are
    configured/reachable, so callers can fall back to rule-based logic."""
    order = {
        "anthropic": [_call_anthropic],
        "openai": [lambda i, p: _call_openai(i, p, want_json)],
        "ollama": [_call_ollama],
        "off": [],
    }.get(PROVIDER)

    if order is None:  # auto
        order = [_call_anthropic, lambda i, p: _call_openai(i, p, want_json), _call_ollama]

    for fn in order:
        result = fn(instructions, prompt)
        if result:
            return result
    return None


def _extract_json(text):
    """Real LLMs sometimes wrap JSON in prose or ```json fences -- pull the
    object out instead of failing the whole request."""
    if not text:
        return None
    text = text.strip()
    text = re.sub(r"^```(json)?", "", text.strip(), flags=re.IGNORECASE).strip()
    text = re.sub(r"```$", "", text.strip()).strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except Exception:
            return None
    return None


# ---------------------------------------------------------------------------
# 1. AI Concierge -- free-form guest chat
# ---------------------------------------------------------------------------
def concierge(message, context=None):
    context = context or {}
    prompt = f"""You are ResortOS AI Concierge for OceanView Resort. Answer briefly, warmly and practically.
Resort context: rooms, dining, activities, housekeeping, maintenance, airport transfer, support.
Guest context: {json.dumps(context, default=str)}
Guest message: {message}
Do not invent exact prices, availability, bookings, or policies. If data is unavailable, say so and suggest contacting reception."""
    ai = _call_ai("You are a helpful hotel concierge. Keep answers under 120 words.", prompt)
    if ai:
        return ai
    text = message.lower()
    if any(k in text for k in ['wifi', 'wi-fi', 'internet']):
        return "Wi-Fi support can be handled by reception. I can also help you raise a service request from ResortOS."
    if any(k in text for k in ['clean', 'towel', 'housekeeping']):
        return "I can help with housekeeping requests such as room cleaning, towels, linen, and amenities. Try Issue Intelligence to send it straight to the team."
    if any(k in text for k in ['dining', 'food', 'restaurant']):
        return "OceanView Resort can route dining requests to the guest-services team. Tell me what you need and I can suggest the right request type."
    if any(k in text for k in ['pool', 'activity', 'activities']):
        return "The resort experience includes pool and activity areas. For live timings or availability, reception can confirm the current schedule."
    return "I’m your ResortOS AI Concierge. I can help with rooms, housekeeping, dining, activities, maintenance requests, and general resort guidance."


# ---------------------------------------------------------------------------
# 2. Operations Insight -- AI analytics over live resort data (owner/manager/admin)
# ---------------------------------------------------------------------------
def operations_insight(metrics):
    prompt = f"""Analyze this resort operations snapshot and give 4 concise, actionable recommendations.
Metrics: {json.dumps(metrics, default=str)}
Return bullet points. Focus on occupancy, open issues, pending work, guest AI activity and low stock. Do not invent facts."""
    ai = _call_ai("You are an operations intelligence assistant for a resort manager.", prompt)
    if ai:
        return ai
    actions = []
    if metrics.get('open_issues', 0):
        actions.append(f"Prioritize the {metrics['open_issues']} open issue(s), especially high-priority maintenance.")
    if metrics.get('pending_tasks', 0):
        actions.append(f"Review {metrics['pending_tasks']} pending task(s) and reassign overdue work if needed.")
    if metrics.get('low_stock', 0):
        actions.append(f"Reorder {metrics['low_stock']} low-stock inventory item(s) before the next busy period.")
    if metrics.get('ai_actions_7d', 0):
        actions.append(f"{metrics['ai_actions_7d']} guest request(s) were auto-routed by AI Intelligence this week -- spot-check the high priority ones.")
    if metrics.get('available', 0):
        actions.append(f"Use the {metrics['available']} available room(s) for upcoming arrivals and avoid unnecessary downtime.")
    return '\n'.join('• ' + x for x in actions) or '• Operations look stable. Continue monitoring live room, issue and task status.'


# ---------------------------------------------------------------------------
# 3a. Structured triage -- staff-entered issue with title/description/category
# ---------------------------------------------------------------------------
def triage_issue(title, description, category='General', room=''):
    prompt = f"""Classify this resort issue.
Title: {title}
Description: {description}
Category supplied: {category}
Room: {room}
Return ONLY valid JSON with keys: department, priority, summary, recommended_action.
Department must be one of Maintenance, Housekeeping, Reception, Manager.
Priority must be Low, Medium, or High."""
    ai = _call_ai("You are a resort operations triage assistant. Return strict JSON only.", prompt, want_json=True)
    parsed = _extract_json(ai)
    if parsed:
        return _normalize_triage(parsed)
    return _normalize_triage(_fallback_classify(f"{title} {description} {category}", category))


# ---------------------------------------------------------------------------
# 3b. Issue Intelligence -- ONE free-text message from a guest, no other
#     fields. The AI reads it, decides the room/category/priority/department,
#     writes a short reply for the guest, and the route layer takes it from
#     there (creates the Issue + routes to the right team).
# ---------------------------------------------------------------------------
def analyze_free_text_issue(message, guest_name=None, room_hint=''):
    prompt = f"""A hotel guest sent this message through the ResortOS "Issue Intelligence" box. There are
no other form fields -- you must work out everything yourself from the text.

Guest name: {guest_name or 'Guest'}
Guest's most recent room on file (use this only if the message does not mention a different room): {room_hint or 'unknown'}
Guest message: "{message}"

Decide:
- title: a short (under 60 characters) title for this issue/request
- category: a short category label (e.g. AC, Electrical, Plumbing, TV, Housekeeping, Billing, General)
- department: which team should handle it -- exactly one of Maintenance, Housekeeping, Reception, Manager
- priority: Low, Medium, or High (High = safety, security, no power/water, or the guest sounds urgent/upset)
- room_number: the room number if the guest mentions one, otherwise null
- summary: one sentence summarizing the issue for staff
- guest_reply: a short, warm, reassuring reply to send back to the guest (1-3 sentences), confirming what you
  understood and that the right team has been notified. Do not promise a specific arrival time.

Return ONLY valid JSON with exactly these keys: title, category, department, priority, room_number, summary, guest_reply."""
    ai = _call_ai("You are a resort operations triage assistant embedded in a guest app. Return strict JSON only, no prose.", prompt, want_json=True)
    parsed = _extract_json(ai)
    if parsed:
        return _normalize_issue_intel(parsed, message, room_hint)
    return _normalize_issue_intel(_fallback_classify(message, ''), message, room_hint, fallback_title=message[:60])


def _fallback_classify(text, category):
    text = f"{text} {category}".lower()
    if any(k in text for k in ['ac', 'air condition', 'electric', 'power', 'leak', 'plumb', 'repair', 'water heater', 'tv', 'wifi', 'wi-fi']):
        department = 'Maintenance'
        cat = 'Maintenance'
    elif any(k in text for k in ['clean', 'towel', 'linen', 'amenit', 'room service', 'housekeeping']):
        department = 'Housekeeping'
        cat = 'Housekeeping'
    elif any(k in text for k in ['bill', 'payment', 'invoice', 'charge', 'refund', 'checkout', 'check-out', 'checkin', 'check-in', 'booking']):
        department = 'Reception'
        cat = 'Billing'
    else:
        department = 'Manager'
        cat = category or 'General'
    priority = 'High' if any(k in text for k in ['urgent', 'danger', 'not working', 'no power', 'flood', 'broken', 'emergency', 'unsafe']) else 'Medium'
    return {
        'department': department,
        'category': cat,
        'priority': priority,
        'summary': f'{department} should review this request.',
        'recommended_action': 'Inspect the issue, update the guest, and record the resolution in ResortOS.',
        'guest_reply': f"Thanks for letting us know -- I've notified our {department} team and flagged this as {priority.lower()} priority. They'll be in touch shortly.",
    }


def _normalize_triage(data):
    allowed_d = {'Maintenance', 'Housekeeping', 'Reception', 'Manager'}
    allowed_p = {'Low', 'Medium', 'High'}
    data['department'] = data.get('department') if data.get('department') in allowed_d else 'Manager'
    data['priority'] = data.get('priority') if data.get('priority') in allowed_p else 'Medium'
    data['summary'] = str(data.get('summary') or 'Review and route this issue.')[:500]
    data['recommended_action'] = str(data.get('recommended_action') or 'Review the issue and update its status.')[:800]
    return data


ROOM_RE = re.compile(r'\b(?:room\s*)?#?(\d{2,4}[A-Za-z]?)\b', re.IGNORECASE)


def _normalize_issue_intel(data, message, room_hint, fallback_title=None):
    allowed_d = {'Maintenance', 'Housekeeping', 'Reception', 'Manager'}
    allowed_p = {'Low', 'Medium', 'High'}
    department = data.get('department') if data.get('department') in allowed_d else 'Manager'
    priority = data.get('priority') if data.get('priority') in allowed_p else 'Medium'
    room_number = data.get('room_number')
    if not room_number:
        m = ROOM_RE.search(message)
        room_number = m.group(1) if m else (room_hint or None)
    title = str(data.get('title') or fallback_title or message[:60])[:120]
    category = str(data.get('category') or 'General')[:60]
    summary = str(data.get('summary') or title)[:500]
    guest_reply = str(data.get('guest_reply') or
                       f"Thanks -- I've notified our {department} team and marked this {priority.lower()} priority.")[:600]
    return {
        'title': title,
        'category': category,
        'department': department,
        'priority': priority,
        'room_number': room_number,
        'summary': summary,
        'guest_reply': guest_reply,
    }