"""
email_builder.py
================
Builds personalised HTML email bodies for each owner.

Each owner gets a single digest email showing:
- Their assigned tasks (with status, due date, priority)
- Blockers they are responsible for resolving
- Decisions assigned to them
- Ambiguous items assigned to them

All content is scoped to a single meeting.
"""

from datetime import date


# ── Palette (matches the UI) ──────────────────────────────────────────────────
_WINE   = "#450920"
_PLUM   = "#A53860"
_MAUVE  = "#DA627D"
_ROSE   = "#FFA5AB"
_CREAM  = "#F9DBBD"
_BG     = "#FDF6EE"
_BORDER = "#E8C9AD"
_TEXT   = "#2C1A0E"
_SOFT   = "#9C6B52"

_STATUS_COLOURS = {
    "open":      ("#2E7D52", "#E8F5EE"),
    "blocked":   ("#B83232", "#FDEAEA"),
    "on_hold":   ("#C47A1E", "#FFF4E0"),
    "confirmed": ("#2E7D52", "#E8F5EE"),
    "deferred":  ("#3D4DA0", "#ECEFFE"),
    "pending":   ("#C47A1E", "#FFF4E0"),
}

_PRIORITY_COLOURS = {
    "high":   ("#B83232", "#FDEAEA"),
    "medium": ("#C47A1E", "#FFF4E0"),
    "low":    ("#2E7D52", "#E8F5EE"),
}


def _badge(text: str, colour_map: dict, default: tuple = (_SOFT, _BG)) -> str:
    if not text:
        return ""
    fg, bg = colour_map.get(text.lower(), default)
    return (
        f'<span style="display:inline-block;background:{bg};color:{fg};'
        f'border:1px solid {fg};border-radius:20px;padding:2px 10px;'
        f'font-size:0.72rem;font-weight:700;text-transform:uppercase;'
        f'letter-spacing:0.5px;">{text}</span>'
    )


def _section(title: str, icon: str, rows_html: str, accent: str = _PLUM) -> str:
    if not rows_html:
        return ""
    return f"""
    <div style="margin-bottom:1.5rem;">
        <div style="font-family:Georgia,serif;font-size:1.05rem;font-weight:600;
                    color:{accent};border-bottom:2px solid {_BORDER};
                    padding-bottom:6px;margin-bottom:10px;">
            {icon}&nbsp;&nbsp;{title}
        </div>
        {rows_html}
    </div>
    """


def _task_row(task: dict, index: int) -> str:
    bg = "#FFFFFF" if index % 2 == 0 else _BG
    status_badge   = _badge(task.get("status", ""),   _STATUS_COLOURS)
    priority_badge = _badge(task.get("priority", ""), _PRIORITY_COLOURS)
    due = task.get("due_date") or "—"
    note = task.get("note") or ""
    note_html = (
        f'<div style="font-size:0.78rem;color:{_SOFT};margin-top:4px;font-style:italic;">'
        f'📎 {note}</div>'
    ) if note else ""
    return f"""
    <div style="background:{bg};border:1px solid {_BORDER};border-radius:8px;
                padding:10px 14px;margin-bottom:6px;">
        <div style="font-weight:600;color:{_TEXT};font-size:0.88rem;margin-bottom:5px;">
            {task.get("title", "Untitled task")}
        </div>
        <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center;">
            {status_badge}
            {priority_badge}
            <span style="font-size:0.76rem;color:{_SOFT};">📅 Due: <strong>{due}</strong></span>
        </div>
        {note_html}
    </div>
    """


def _blocker_row(blocker: dict, index: int) -> str:
    bg = "#FFFFFF" if index % 2 == 0 else _BG
    ticket = blocker.get("ticket") or ""
    ticket_html = (
        f'<span style="font-size:0.76rem;color:{_SOFT};margin-left:8px;">🎫 {ticket}</span>'
    ) if ticket else ""
    return f"""
    <div style="background:{bg};border:1px solid #FFCCCC;border-radius:8px;
                padding:10px 14px;margin-bottom:6px;border-left:4px solid #B83232;">
        <div style="font-weight:600;color:{_TEXT};font-size:0.88rem;margin-bottom:4px;">
            🚧 {blocker.get("task", "Unnamed task")}
        </div>
        <div style="font-size:0.82rem;color:#B83232;margin-bottom:3px;">
            <strong>Blocked by:</strong> {blocker.get("blocked_by", "—")}
        </div>
        {ticket_html}
    </div>
    """


def _decision_row(decision: dict, index: int) -> str:
    bg = "#FFFFFF" if index % 2 == 0 else _BG
    status_badge = _badge(decision.get("status", ""), _STATUS_COLOURS)
    rationale    = decision.get("rationale") or ""
    rationale_html = (
        f'<div style="font-size:0.78rem;color:{_SOFT};margin-top:4px;">'
        f'💡 {rationale}</div>'
    ) if rationale else ""
    return f"""
    <div style="background:{bg};border:1px solid {_BORDER};border-radius:8px;
                padding:10px 14px;margin-bottom:6px;">
        <div style="font-weight:600;color:{_TEXT};font-size:0.88rem;margin-bottom:5px;">
            {decision.get("decision", "Unnamed decision")}
        </div>
        <div>{status_badge}</div>
        {rationale_html}
    </div>
    """


def _ambiguous_row(item: dict, index: int) -> str:
    bg = "#FFFFFF" if index % 2 == 0 else _BG
    note = item.get("note") or ""
    note_html = (
        f'<div style="font-size:0.78rem;color:{_SOFT};margin-top:4px;">🔍 {note}</div>'
    ) if note else ""
    return f"""
    <div style="background:{bg};border:1px solid {_BORDER};border-radius:8px;
                padding:10px 14px;margin-bottom:6px;border-left:4px solid {_MAUVE};">
        <div style="font-weight:600;color:{_TEXT};font-size:0.88rem;">
            ❓ {item.get("description", "Unnamed item")}
        </div>
        {note_html}
    </div>
    """


# ── Public API ────────────────────────────────────────────────────────────────

def build_email(
    owner_name: str,
    meeting_title: str,
    meeting_date: str,
    tasks: list[dict],
    blockers: list[dict],
    decisions: list[dict],
    ambiguous: list[dict],
) -> str:
    """
    Build a complete HTML email body for one owner.

    Args:
        owner_name:    Full name of the recipient (e.g. "Dev Soni").
        meeting_title: Title of the meeting.
        meeting_date:  ISO 8601 date string.
        tasks:         List of task dicts assigned to this owner.
        blockers:      List of blocker dicts assigned to this owner.
        decisions:     List of decision dicts assigned to this owner.
        ambiguous:     List of ambiguous dicts assigned to this owner.

    Returns:
        HTML string ready to send as email body.
    """
    first_name = owner_name.split()[0] if owner_name else "there"
    today      = date.today().strftime("%B %d, %Y")

    # Build section HTML
    tasks_html     = "".join(_task_row(t, i)     for i, t in enumerate(tasks))
    blockers_html  = "".join(_blocker_row(b, i)  for i, b in enumerate(blockers))
    decisions_html = "".join(_decision_row(d, i) for i, d in enumerate(decisions))
    ambiguous_html = "".join(_ambiguous_row(a, i) for i, a in enumerate(ambiguous))

    total = len(tasks) + len(blockers) + len(decisions) + len(ambiguous)

    body = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
    <body style="margin:0;padding:0;background:#F0E8DF;font-family:'DM Sans',Arial,sans-serif;">

    <table width="100%" cellpadding="0" cellspacing="0" style="background:#F0E8DF;padding:24px 0;">
    <tr><td align="center">
    <table width="620" cellpadding="0" cellspacing="0" style="max-width:620px;width:100%;">

        <!-- Header -->
        <tr>
            <td style="background:linear-gradient(135deg,{_WINE},{_PLUM});
                        border-radius:14px 14px 0 0;padding:28px 32px 24px;">
                <div style="font-family:Georgia,serif;font-size:1.6rem;color:#FFFFFF;
                            font-weight:600;letter-spacing:-0.5px;">
                    🎙️ Meeting Intelligence
                </div>
                <div style="font-size:0.85rem;color:{_ROSE};margin-top:4px;">
                    Action Items Summary &nbsp;·&nbsp; {today}
                </div>
            </td>
        </tr>

        <!-- Greeting -->
        <tr>
            <td style="background:#FFFFFF;padding:24px 32px 12px;
                        border-left:1px solid {_BORDER};border-right:1px solid {_BORDER};">
                <p style="font-size:1rem;color:{_TEXT};margin:0 0 6px;">
                    Hi <strong>{first_name}</strong>,
                </p>
                <p style="font-size:0.88rem;color:{_SOFT};margin:0 0 16px;line-height:1.5;">
                    Here is your action item summary from the meeting
                    <strong style="color:{_WINE};">{meeting_title}</strong>
                    held on {meeting_date}.
                    You have <strong style="color:{_PLUM};">{total} item{"s" if total != 1 else ""}</strong>
                    assigned to you.
                </p>

                <!-- Summary strip -->
                <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:20px;">
                <tr>
                    <td align="center" style="background:{_BG};border:1.5px solid {_BORDER};
                        border-radius:10px;padding:12px;">
                        <table><tr>
                            <td style="text-align:center;padding:0 16px;">
                                <div style="font-family:Georgia,serif;font-size:1.6rem;color:{_PLUM};">{len(tasks)}</div>
                                <div style="font-size:0.65rem;text-transform:uppercase;letter-spacing:1px;color:{_SOFT};">Tasks</div>
                            </td>
                            <td style="text-align:center;padding:0 16px;border-left:1px solid {_BORDER};">
                                <div style="font-family:Georgia,serif;font-size:1.6rem;color:{_PLUM};">{len(blockers)}</div>
                                <div style="font-size:0.65rem;text-transform:uppercase;letter-spacing:1px;color:{_SOFT};">Blockers</div>
                            </td>
                            <td style="text-align:center;padding:0 16px;border-left:1px solid {_BORDER};">
                                <div style="font-family:Georgia,serif;font-size:1.6rem;color:{_PLUM};">{len(decisions)}</div>
                                <div style="font-size:0.65rem;text-transform:uppercase;letter-spacing:1px;color:{_SOFT};">Decisions</div>
                            </td>
                            <td style="text-align:center;padding:0 16px;border-left:1px solid {_BORDER};">
                                <div style="font-family:Georgia,serif;font-size:1.6rem;color:{_PLUM};">{len(ambiguous)}</div>
                                <div style="font-size:0.65rem;text-transform:uppercase;letter-spacing:1px;color:{_SOFT};">Ambiguous</div>
                            </td>
                        </tr></table>
                    </td>
                </tr>
                </table>
            </td>
        </tr>

        <!-- Content sections -->
        <tr>
            <td style="background:#FFFFFF;padding:4px 32px 24px;
                        border-left:1px solid {_BORDER};border-right:1px solid {_BORDER};">

                {_section("Your Tasks", "📋", tasks_html, _WINE) if tasks else ""}
                {_section("Blockers You Own", "🚧", blockers_html, "#B83232") if blockers else ""}
                {_section("Decisions", "✅", decisions_html, "#2E7D52") if decisions else ""}
                {_section("Ambiguous Items", "❓", ambiguous_html, _MAUVE) if ambiguous else ""}

                {"<p style='color:#9C6B52;font-style:italic;font-size:0.85rem;'>No items assigned to you in this meeting.</p>" if total == 0 else ""}
            </td>
        </tr>

        <!-- Footer -->
        <tr>
            <td style="background:{_BG};border:1px solid {_BORDER};
                        border-radius:0 0 14px 14px;padding:16px 32px;text-align:center;">
                <p style="font-size:0.75rem;color:{_SOFT};margin:0;line-height:1.6;">
                    This notification was generated by <strong>Intelligence Meeting Bot</strong>.<br>
                    Please do not reply to this email.
                </p>
            </td>
        </tr>

    </table>
    </td></tr>
    </table>

    </body>
    </html>
    """
    return body


def owner_to_email(owner_name: str, domain: str = "infobeans.com") -> str:
    """
    Convert a full name to an email address.

    Args:
        owner_name: Full name with space e.g. "Dev Soni"
        domain:     Email domain, defaults to infobeans.com

    Returns:
        Email string e.g. "dev.soni@infobeans.com"

    Examples:
        "Dev Soni"      → "dev.soni@infobeans.com"
        "Priya Sharma"  → "priya.sharma@infobeans.com"
        "Meera Joshi"   → "meera.joshi@infobeans.com"
    """
    if not owner_name or not owner_name.strip():
        return ""
    parts = owner_name.strip().lower().split()
    if len(parts) < 2:
        return f"{parts[0]}@{domain}"
    return f"{parts[0]}.{parts[-1]}@{domain}"
