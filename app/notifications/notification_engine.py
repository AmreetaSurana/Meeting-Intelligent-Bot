"""
notification_engine.py
======================
Reads all owners from a meeting's database tables, groups their
assigned items by owner, builds a personalised digest email for
each owner, and dispatches via Gmail API.

Usage
-----
    # Send notifications for one meeting
    from app.notifications.notification_engine import notify_meeting
    results = notify_meeting("meet_2026_05_29")

    # Send for all meetings
    from app.notifications.notification_engine import notify_all_meetings
    notify_all_meetings()

    # CLI
    python -m app.notifications.notification_engine meet_2026_05_29
"""

import logging
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from app.db.db_schema import get_connection, list_meeting_dbs
from app.notifications.email_builder import build_email, owner_to_email
from app.notifications.gmail_client import send_bulk

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════
#  Data extraction from DB
# ════════════════════════════════════════════════════════

def _get_meeting_meta(conn) -> dict:
    """Fetch meeting title and date from the meeting table."""
    row = conn.execute("SELECT title, date FROM meetings LIMIT 1").fetchone()
    if row:
        return {"title": row["title"] or "Meeting", "date": row["date"] or ""}
    return {"title": "Meeting", "date": ""}


def _collect_by_owner(conn) -> dict[str, dict]:
    """
    Query all four tables and group items by owner name.

    Returns:
        Dict keyed by owner name, each value is:
        {
            tasks:     [list of task dicts],
            blockers:  [list of blocker dicts],
            decisions: [list of decision dicts],
            ambiguous: [list of ambiguous dicts],
        }
    """
    owners: dict[str, dict] = defaultdict(lambda: {
        "tasks": [], "blockers": [], "decisions": [], "ambiguous": []
    })

    # Tasks
    for row in conn.execute(
        "SELECT * FROM action_items WHERE owner IS NOT NULL AND owner != ''"
    ).fetchall():
        owner = row["owner"].strip()
        if owner:
            owners[owner]["tasks"].append(dict(row))

    # Blockers — owner = resolver
    for row in conn.execute(
        "SELECT * FROM blockers WHERE owner IS NOT NULL AND owner != ''"
    ).fetchall():
        owner = row["owner"].strip()
        if owner:
            owners[owner]["blockers"].append(dict(row))

    # Decisions — no direct owner column in decisions table
    # so skip — decisions are broadcast to all attendees instead
    # (see notify_meeting for broadcast logic)

    # Ambiguous
    for row in conn.execute(
        "SELECT * FROM ambiguous WHERE owner IS NOT NULL AND owner != ''"
    ).fetchall():
        owner = row["owner"].strip()
        if owner:
            owners[owner]["ambiguous"].append(dict(row))

    return owners


def _get_all_decisions(conn) -> list[dict]:
    """Fetch all decisions — these are sent to all attendees as a broadcast."""
    return [dict(r) for r in conn.execute("SELECT * FROM decisions").fetchall()]


def _get_attendees(conn) -> list[str]:
    """Fetch all attendee names for this meeting."""
    return [r["name"] for r in conn.execute("SELECT name FROM attendees").fetchall()]


# ════════════════════════════════════════════════════════
#  Notification builder
# ════════════════════════════════════════════════════════

def build_notifications(meeting_id: str) -> list[dict]:
    """
    Build a list of notification dicts for every owner in this meeting.

    Each notification covers:
    - All tasks assigned to that owner
    - All blockers the owner is responsible for resolving
    - All decisions (broadcast to every attendee)
    - All ambiguous items assigned to that owner

    Args:
        meeting_id: The meeting identifier (used to open the .db file).

    Returns:
        List of dicts: [{to, subject, html_body, owner_name}]
    """
    conn = get_connection()
    try:
        meta       = _get_meeting_meta(conn)
        by_owner   = _collect_by_owner(conn)
        decisions  = _get_all_decisions(conn)
        attendees  = _get_attendees(conn)
    finally:
        conn.close()

    notifications = []

    # ── Per-owner notifications ───────────────────────────────────────────────
    # Union of owners (from tasks+blockers+ambiguous) and attendees
    all_people = set(by_owner.keys()) | set(attendees)

    for person in sorted(all_people):
        if not person.strip():
            continue

        assigned = by_owner.get(person, {
            "tasks": [], "blockers": [], "decisions": [], "ambiguous": []
        })

        # Everyone gets the decisions section
        person_decisions = decisions

        email_address = owner_to_email(person)
        if not email_address:
            logger.warning("Could not build email for owner: %s", person)
            continue

        html_body = build_email(
            owner_name    = person,
            meeting_title = meta["title"],
            meeting_date  = meta["date"],
            tasks         = assigned["tasks"],
            blockers      = assigned["blockers"],
            decisions     = person_decisions,
            ambiguous     = assigned["ambiguous"],
        )

        subject = (
            f"[Meeting Bot] Your action items — {meta['title']} ({meta['date']})"
        )

        notifications.append({
            "to":         email_address,
            "subject":    subject,
            "html_body":  html_body,
            "owner_name": person,
        })

        logger.info(
            "Built notification for %s (%s) — %d tasks, %d blockers, "
            "%d decisions, %d ambiguous",
            person, email_address,
            len(assigned["tasks"]), len(assigned["blockers"]),
            len(person_decisions), len(assigned["ambiguous"]),
        )

    return notifications


# ════════════════════════════════════════════════════════
#  Public send functions
# ════════════════════════════════════════════════════════

def notify_meeting(meeting_id: str, dry_run: bool = False) -> dict:
    """
    Build and send notifications for all owners in a single meeting.

    Args:
        meeting_id: The meeting identifier.
        dry_run:    If True, builds notifications but does not send them.
                    Useful for testing email content before sending.

    Returns:
        Summary dict: {meeting_id, total, sent, failed, failures, dry_run}
    """
    logger.info("Building notifications for meeting: %s", meeting_id)
    notifications = build_notifications(meeting_id)

    if not notifications:
        logger.info("No owners found in meeting %s — nothing to send.", meeting_id)
        return {"meeting_id": meeting_id, "total": 0, "sent": 0, "failed": 0,
                "failures": [], "dry_run": dry_run}

    if dry_run:
        logger.info(
            "DRY RUN — would send %d emails for meeting %s",
            len(notifications), meeting_id
        )
        for n in notifications:
            logger.info("  → %s (%s)", n["owner_name"], n["to"])
        return {
            "meeting_id": meeting_id,
            "total":      len(notifications),
            "sent":       0,
            "failed":     0,
            "failures":   [],
            "dry_run":    True,
            "recipients": [{"name": n["owner_name"], "email": n["to"]}
                           for n in notifications],
        }

    results = send_bulk(notifications)
    results["meeting_id"] = meeting_id
    results["total"]      = len(notifications)
    results["dry_run"]    = False

    logger.info(
        "Meeting %s — sent: %d, failed: %d",
        meeting_id, results["sent"], results["failed"]
    )
    if results["failures"]:
        logger.warning("Failed recipients: %s", results["failures"])

    return results


def notify_all_meetings(dry_run: bool = False) -> list[dict]:
    """
    Send notifications for every meeting in the database directory.

    Args:
        dry_run: If True, builds but does not send.

    Returns:
        List of result dicts, one per meeting.
    """
    meetings = list_meeting_dbs()
    if not meetings:
        logger.info("No meetings found.")
        return []

    all_results = []
    for m in meetings:
        result = notify_meeting(m["id"], dry_run=dry_run)
        all_results.append(result)

    total_sent   = sum(r.get("sent", 0)   for r in all_results)
    total_failed = sum(r.get("failed", 0) for r in all_results)
    logger.info(
        "All meetings — total sent: %d, total failed: %d",
        total_sent, total_failed
    )
    return all_results


# ════════════════════════════════════════════════════════
#  CLI entry point
# ════════════════════════════════════════════════════════

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)s  %(message)s"
    )

    args = sys.argv[1:]

    dry = "--dry-run" in args
    args = [a for a in args if a != "--dry-run"]

    if args:
        meeting_id = args[0]
        result     = notify_meeting(meeting_id, dry_run=dry)
        print(f"\nResult for {meeting_id}:")
        print(f"  Total recipients : {result['total']}")
        print(f"  Sent             : {result['sent']}")
        print(f"  Failed           : {result['failed']}")
        if result["failures"]:
            print(f"  Failed addresses : {', '.join(result['failures'])}")
    else:
        print("Usage:")
        print("  python -m app.notifications.notification_engine <meeting_id> [--dry-run]")
        print("  python -m app.notifications.notification_engine --dry-run   (all meetings)")
        results = notify_all_meetings(dry_run=dry)
        for r in results:
            print(f"  {r['meeting_id']}: sent={r['sent']} failed={r['failed']}")