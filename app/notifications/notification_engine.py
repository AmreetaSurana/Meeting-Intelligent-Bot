"""
notification_engine.py
======================
Reads owners from the SELECTED meeting only, groups their assigned items
by owner, builds a personalised digest email per owner, and sends via Gmail.

Key fix: every query is filtered by meeting_id — data from other meetings
is never touched, and only attendees of the selected meeting receive emails.

Usage
-----
    from app.notifications.notification_engine import notify_meeting
    results = notify_meeting("meet_2026_06_03_a3f7c1b8")
    results = notify_meeting("meet_2026_06_03_a3f7c1b8", dry_run=True)

    # CLI
    python -m app.notifications.notification_engine meet_2026_06_03_a3f7c1b8
    python -m app.notifications.notification_engine meet_2026_06_03_a3f7c1b8 --dry-run
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
#  Data extraction — ALL queries filtered by meeting_id
# ════════════════════════════════════════════════════════

def _get_meeting_meta(conn, meeting_id: str) -> dict:
    """
    Fetch title and date for this specific meeting only.

    FIX: was 'SELECT ... FROM meetings LIMIT 1' with no WHERE clause —
    always returned the first meeting's metadata regardless of which
    meeting was selected. Now correctly filters by meeting_id.
    """
    row = conn.execute(
        "SELECT title, date FROM meetings WHERE id = ?",
        (meeting_id,)
    ).fetchone()
    if row:
        return {
            "title": row["title"] or "Untitled Meeting",
            "date":  row["date"]  or "",
        }
    return {"title": "Untitled Meeting", "date": ""}


def _collect_by_owner(conn, meeting_id: str) -> dict:
    """
    Group action_items, blockers, and ambiguous rows by owner name,
    scoped strictly to this meeting.

    FIX: was querying full tables with no WHERE clause — returned owners
    and items from ALL meetings combined. Now every query includes
    AND meeting_id = ? to restrict results to the selected meeting only.

    Returns:
        defaultdict keyed by owner name:
        {"tasks": [...], "blockers": [...], "ambiguous": [...]}
    """
    owners = defaultdict(lambda: {
        "tasks": [], "blockers": [], "ambiguous": []
    })

    # Tasks assigned to a named owner in this meeting
    for row in conn.execute(
    """
        SELECT * FROM action_items
        WHERE meeting_id = ?
        AND owner IS NOT NULL
        AND TRIM(owner) != ''
        ORDER BY id
        """,
        (meeting_id,)
    ).fetchall():

        raw_owner = row["owner"].strip()

        owner_list = [
            x.strip()
            for x in raw_owner.replace("&", ",")
                            .replace(" and ", ",")
                            .split(",")
            if x.strip()
        ]

        for owner in owner_list:
            owners[owner]["tasks"].append(dict(row))

    # Blockers whose resolver is in the owner column, in this meeting
    for row in conn.execute(
        """
        SELECT * FROM blockers
        WHERE meeting_id = ?
          AND owner IS NOT NULL
          AND TRIM(owner) != ''
        ORDER BY id
        """,
        (meeting_id,)
    ).fetchall():
        raw_owner = row["owner"].strip()

        owner_list = [
            x.strip()
            for x in raw_owner.replace("&", ",")
                            .replace(" and ", ",")
                            .split(",")
            if x.strip()
        ]

        for owner in owner_list:
            owners[owner]["blockers"].append(dict(row))

    # Ambiguous items with a named owner, in this meeting
    for row in conn.execute(
        """
        SELECT * FROM ambiguous
        WHERE meeting_id = ?
          AND owner IS NOT NULL
          AND TRIM(owner) != ''
        ORDER BY id
        """,
        (meeting_id,)
    ).fetchall():
        raw_owner = row["owner"].strip()

        owner_list = [
            x.strip()
            for x in raw_owner.replace("&", ",")
                            .replace(" and ", ",")   
                            .split(",")
            if x.strip()
        ]

        for owner in owner_list:
            owners[owner]["ambiguous"].append(dict(row))

    return owners


def _get_decisions(conn, meeting_id: str) -> list[dict]:
    """
    Fetch all decisions for this meeting only.
    Decisions are broadcast to every attendee of this meeting.

    FIX: was querying all decisions across all meetings.
    """
    return [dict(r) for r in conn.execute(
        "SELECT * FROM decisions WHERE meeting_id = ? ORDER BY id",
        (meeting_id,)
    ).fetchall()]


def _get_attendees(conn, meeting_id: str) -> list[str]:
    """
    Fetch attendee names for this meeting only.

    FIX: was querying all attendees across all meetings, causing
    people from other meetings to receive emails.
    """
    return [
        r["name"].strip()
        for r in conn.execute(
            "SELECT name FROM attendees WHERE meeting_id = ? ORDER BY id",
            (meeting_id,)
        ).fetchall()
        if r["name"] and r["name"].strip()
    ]


# ════════════════════════════════════════════════════════
#  Notification builder
# ════════════════════════════════════════════════════════

def build_notifications(meeting_id: str) -> list[dict]:
    """
    Build a personalised notification for every person in the selected meeting.

    Who receives an email:
    - Every named attendee of THIS meeting (not other meetings)
    - Anyone who owns at least one task, blocker or ambiguous item in THIS meeting

    What each email contains:
    - Tasks assigned to that person (from this meeting)
    - Blockers they own (from this meeting)
    - All decisions from this meeting (broadcast to all attendees)
    - Ambiguous items assigned to them (from this meeting)

    Args:
        meeting_id: The unique meeting identifier to send notifications for.

    Returns:
        List of notification dicts: [{to, subject, html_body, owner_name}]
    """
    # get_connection() with no arguments uses the default DB_PATH (meetings.db)
    # Do NOT pass meeting_id here — it is not a file path
    conn = get_connection()
    try:
        meta      = _get_meeting_meta(conn, meeting_id)
        by_owner  = _collect_by_owner(conn, meeting_id)
        decisions = _get_decisions(conn, meeting_id)
        attendees = _get_attendees(conn, meeting_id)
    finally:
        conn.close()

    # Only people in THIS meeting — union of named owners and listed attendees
    all_people = set(by_owner.keys()) | set(attendees)

    if not all_people:
        logger.warning("No people found for meeting %s.", meeting_id)
        return []

    notifications = []

    for person in sorted(all_people):
        if not person:
            continue

        email_address = owner_to_email(person)
        if not email_address:
            logger.warning("Skipping %s — could not build email address.", person)
            continue

        assigned = by_owner.get(person, {
            "tasks": [], "blockers": [], "ambiguous": []
        })

        html_body = build_email(
            owner_name    = person,
            meeting_title = meta["title"],
            meeting_date  = meta["date"],
            tasks         = assigned["tasks"],
            blockers      = assigned["blockers"],
            decisions     = decisions,        # broadcast to all attendees
            ambiguous     = assigned["ambiguous"],
        )

        subject = (
            f"[Meeting Bot] Your action items — "
            f"{meta['title']} ({meta['date']})"
        )

        notifications.append({
            "to":         email_address,
            "subject":    subject,
            "html_body":  html_body,
            "owner_name": person,
        })

        logger.info(
            "Notification for %-22s (%s) | tasks=%d  blockers=%d  "
            "decisions=%d  ambiguous=%d",
            person, email_address,
            len(assigned["tasks"]),
            len(assigned["blockers"]),
            len(decisions),
            len(assigned["ambiguous"]),
        )

    return notifications


# ════════════════════════════════════════════════════════
#  Public API
# ════════════════════════════════════════════════════════

def notify_meeting(meeting_id: str, dry_run: bool = False) -> dict:
    """
    Build and optionally send notifications for the selected meeting.

    Args:
        meeting_id: The unique meeting identifier.
        dry_run:    If True, returns recipient list without sending any emails.

    Returns:
        {
            meeting_id:  str,
            total:       int,
            sent:        int,
            failed:      int,
            failures:    list[str],
            dry_run:     bool,
            recipients:  list[{name, email}]
        }
    """
    logger.info("Building notifications for meeting: %s", meeting_id)
    notifications = build_notifications(meeting_id)

    recipients = [
        {"name": n["owner_name"], "email": n["to"]}
        for n in notifications
    ]

    base = {
        "meeting_id": meeting_id,
        "total":      len(notifications),
        "failures":   [],
        "dry_run":    dry_run,
        "recipients": recipients,
    }

    if not notifications:
        logger.info("No recipients for meeting %s.", meeting_id)
        return {**base, "sent": 0, "failed": 0}

    if dry_run:
        logger.info(
            "DRY RUN — %d emails would be sent for meeting %s",
            len(notifications), meeting_id,
        )
        for n in notifications:
            logger.info("  → %-22s  %s", n["owner_name"], n["to"])
        return {**base, "sent": 0, "failed": 0}

    results = send_bulk(notifications)
    logger.info(
        "Meeting %s complete — sent: %d  failed: %d",
        meeting_id, results["sent"], results["failed"],
    )
    if results["failures"]:
        logger.warning("Failed: %s", results["failures"])

    return {
        **base,
        "sent":     results["sent"],
        "failed":   results["failed"],
        "failures": results["failures"],
    }


def notify_all_meetings(dry_run: bool = False) -> list[dict]:
    """Send notifications for every stored meeting."""
    meetings = list_meeting_dbs()
    if not meetings:
        logger.info("No meetings found.")
        return []

    all_results = [notify_meeting(m["id"], dry_run=dry_run) for m in meetings]
    logger.info(
        "All meetings — sent: %d  failed: %d",
        sum(r.get("sent", 0)   for r in all_results),
        sum(r.get("failed", 0) for r in all_results),
    )
    return all_results


# ════════════════════════════════════════════════════════
#  CLI
# ════════════════════════════════════════════════════════

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)s  %(message)s",
    )

    args    = sys.argv[1:]
    dry_run = "--dry-run" in args
    args    = [a for a in args if a != "--dry-run"]

    if args:
        result = notify_meeting(args[0], dry_run=dry_run)
        print(f"\nMeeting : {result['meeting_id']}")
        print(f"Total   : {result['total']}")
        print(f"Sent    : {result['sent']}")
        print(f"Failed  : {result['failed']}")
        if dry_run:
            print("\nRecipients:")
            for r in result.get("recipients", []):
                print(f"  → {r['name']:<25} {r['email']}")
    else:
        print("Usage: python -m app.notifications.notification_engine <meeting_id> [--dry-run]")
        for r in notify_all_meetings(dry_run=dry_run):
            print(f"  {r['meeting_id']}: sent={r['sent']} failed={r['failed']}")
