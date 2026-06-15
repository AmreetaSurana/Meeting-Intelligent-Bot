"""
app.py
=========
Streamlit UI for the meeting extraction pipeline.
"""

import json
import sys
import time
import uuid
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.pipeline.llm_call import llm_for_structured_json
from app.pipeline.validator import clean_json_response
from app.db.db_schema import initialise_db, get_connection
from app.db.db_writer import save_extraction
from app.notifications.notification_engine import notify_meeting
from flask import Flask

app = Flask(__name__)

@app.route("/")
def home():
    return

st.set_page_config(
    page_title="Intelligence Meeting Bot",
    page_icon="🎙️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=DM+Sans:opsz,wght@9..40,300;9..40,400;9..40,500;9..40,600&display=swap');

:root {
    --cream:     #F9DBBD;
    --rose:      #FFA5AB;
    --mauve:     #DA627D;
    --plum:      #A53860;
    --wine:      #450920;
    --bg:        #FDF6EE;
    --bg-soft:   #F7EDE0;
    --bg-card:   #FFFFFF;
    --border:    #E8C9AD;
    --text-dark: #2C1A0E;
    --text-mid:  #6B3A2A;
    --text-soft: #9C6B52;
    --amber:     #C47A1E;
    --amber-lt:  #FFF4E0;
    --green:     #2E7D52;
    --green-lt:  #E8F5EE;
}

html, body, [class*="css"] {
    font-family: 'DM Sans', sans-serif;
    color: var(--text-dark) !important;
}
.stApp {
    background: var(--bg) !important;
    min-height: 100vh;
}
.stApp::before {
    content: '';
    position: fixed; inset: 0;
    background:
        radial-gradient(ellipse at 10% 20%, rgba(218,98,125,0.06) 0%, transparent 55%),
        radial-gradient(ellipse at 90% 80%, rgba(59,122,122,0.05) 0%, transparent 55%);
    pointer-events: none; z-index: 0;
}
#MainMenu, footer, header { visibility: hidden; }
.block-container {
    padding: 1.5rem 2.5rem 4rem;
    max-width: 1600px;
    position: relative; z-index: 1;
}

/* Hero */
.hero { text-align: center; padding: 2rem 0 1.5rem; }
.hero-title {
    font-family: 'DM Serif Display', serif;
    font-size: 3rem; color: var(--wine);
    line-height: 1.1; letter-spacing: -1px; margin: 0;
}
.hero-title em { color: var(--mauve); font-style: italic; }
.hero-sub { font-size: 0.95rem; color: var(--text-soft); margin-top: 0.5rem; letter-spacing: 0.5px; }
.divider-line {
    width: 60px; height: 3px;
    background: linear-gradient(90deg, var(--mauve), var(--rose));
    margin: 1rem auto 0; border-radius: 2px;
}

/* Stat boxes */
.stat-row { display: grid; grid-template-columns: repeat(4,1fr); gap: 0.8rem; margin: 1rem 0 1.2rem; }
.stat-box {
    background: var(--bg-card); border: 1.5px solid var(--border);
    border-radius: 14px; padding: 1rem; text-align: center;
    box-shadow: 0 2px 8px rgba(69,9,32,0.07);
}
.stat-num { font-family: 'DM Serif Display', serif; font-size: 2rem; color: var(--plum); line-height: 1; }
.stat-lbl { font-size: 0.7rem; color: var(--text-soft); text-transform: uppercase; letter-spacing: 1px; margin-top: 0.2rem; font-weight: 600; }

/* Section label */
.sec-label {
    font-family: 'DM Serif Display', serif; font-size: 1.1rem; color: var(--wine);
    margin: 1.2rem 0 0.5rem; display: flex; align-items: center; gap: 0.5rem;
}

/* Table container — the bordered box that wraps everything */
.table-box {
    background: var(--bg-card);
    border: 1.5px solid var(--border);
    border-radius: 12px;
    padding: 1rem 1rem 0.6rem 1rem;
    margin-bottom: 0.5rem;
    box-shadow: 0 2px 8px rgba(69,9,32,0.06);
}

/* Table action bar above the table */
.table-action-bar {
    display: flex; align-items: center; gap: 0.5rem;
    margin-bottom: 0.8rem;
    padding-bottom: 0.8rem;
    border-bottom: 1px solid var(--border);
}

/* Column headers inside our custom tables */
.tbl-hdr {
    font-size: 0.7rem; font-weight: 700; text-transform: uppercase;
    letter-spacing: 0.8px; color: var(--wine);
    padding: 0 0 6px 4px;
    border-bottom: 2px solid var(--border);
    margin-bottom: 4px;
}
.tbl-id {
    font-size: 0.75rem; color: var(--text-soft);
    font-weight: 600; padding-top: 7px; padding-left: 4px;
}

/* Expander styling */
.streamlit-expanderHeader {
    background: var(--bg-soft) !important;
    border: 1.5px solid var(--border) !important;
    border-radius: 10px !important;
    color: var(--wine) !important;
    font-family: 'DM Serif Display', serif !important;
    font-size: 1rem !important;
    font-weight: 600 !important;
}
.streamlit-expanderContent {
    border: 1.5px solid var(--border) !important;
    border-top: none !important;
    border-radius: 0 0 10px 10px !important;
    background: var(--bg-card) !important;
    padding: 0.8rem !important;
}

/* Buttons */
.stButton > button {
    background: linear-gradient(135deg, var(--wine), var(--plum)) !important;
    color: #FFFFFF !important; -webkit-text-fill-color: #FFFFFF !important;
    border: none !important; border-radius: 8px !important;
    font-family: 'DM Sans', sans-serif !important; font-weight: 700 !important;
    font-size: 0.85rem !important; padding: 0.45rem 1.1rem !important;
    box-shadow: 0 2px 6px rgba(69,9,32,0.18) !important;
    transition: opacity 0.2s !important; white-space: nowrap !important;
}
.stButton > button:hover { opacity: 0.86 !important; }
.stButton > button p, .stButton > button span, .stButton > button div {
    color: #FFFFFF !important; -webkit-text-fill-color: #FFFFFF !important;
}

/* Delete button — red variant */
.del-btn .stButton > button {
    background: linear-gradient(135deg, #8B1A1A, #B83232) !important;
}

/* File uploader */
[data-testid="stFileUploader"] {
    background: var(--bg-soft) !important;
    border: 2px dashed var(--border) !important;
    border-radius: 12px !important;
}

/* Selectbox */
.stSelectbox > div > div {
    background: var(--bg-card) !important;
    border: 1.5px solid var(--border) !important;
    border-radius: 8px !important; color: var(--text-dark) !important;
}

/* Text inputs */
.stTextInput > div > div > input {
    background: var(--bg-card) !important;
    border: 1.5px solid var(--border) !important;
    border-radius: 7px !important;
    color: #000000 !important;
    -webkit-text-fill-color: #000000 !important;
    font-size: 0.85rem !important;
}
.stTextInput > div > div > input::placeholder { color: #aaa !important; }

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
    background: var(--bg-soft) !important; border-radius: 10px !important;
    border: 1.5px solid var(--border) !important; padding: 3px !important; gap: 3px !important;
}
.stTabs [data-baseweb="tab"] {
    background: transparent !important; color: var(--text-soft) !important;
    border-radius: 8px !important; font-weight: 600 !important; font-size: 0.85rem !important;
}
.stTabs [aria-selected="true"] {
    background: var(--wine) !important; color: #FFFFFF !important;
    -webkit-text-fill-color: #FFFFFF !important;
}
            
textarea {
    min-height: 100px !important;
    resize: vertical !important;
    white-space: pre-wrap !important;
    overflow-wrap: break-word !important;
}

/* Pipeline steps */
.p-step {
    display: flex; align-items: center; gap: 0.7rem;
    padding: 0.5rem 0.9rem; border-radius: 7px;
    margin-bottom: 0.35rem; font-size: 0.85rem; font-weight: 500;
}
.p-done    { background: var(--green-lt); color: var(--green); border: 1px solid rgba(46,125,82,0.2); }
.p-running { background: var(--amber-lt); color: var(--amber); border: 1px solid rgba(196,122,30,0.25); }
.p-wait    { background: var(--bg-soft);  color: var(--text-soft); border: 1px solid var(--border); }

/* Attendee pills */
.att-pill {
    display: inline-block; background: var(--cream); border: 1.5px solid var(--rose);
    border-radius: 20px; padding: 3px 12px; font-size: 0.78rem; color: var(--wine);
    font-weight: 600; margin: 2px 3px;
}

/* Delete meeting danger zone */
.danger-zone {
    background: #FFF5F5; border: 1.5px solid #FFCCCC;
    border-radius: 10px; padding: 0.8rem 1rem; margin-top: 1rem;
}

hr { border-color: var(--border) !important; }
::-webkit-scrollbar { width: 5px; }
::-webkit-scrollbar-track { background: var(--bg-soft); }
::-webkit-scrollbar-thumb { background: var(--mauve); border-radius: 3px; }
p, span, label { color: var(--text-dark); }
</style>
""", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════
#  DB helpers
# ════════════════════════════════════════════════════════

@st.cache_data(ttl=5)
def load_meetings() -> list[dict]:
    try:
        conn = get_connection()
        rows = conn.execute(
            "SELECT id, date, title FROM meetings ORDER BY date DESC"
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception:
        return []


def load_meeting_data(meeting_id: str) -> dict:
    conn = get_connection()
    try:
        def fetch(table):
            return [dict(r) for r in conn.execute(
                f"SELECT * FROM {table} WHERE meeting_id=? ORDER BY id",
                (meeting_id,)
            ).fetchall()]
        attendees = [r["name"] for r in conn.execute(
            "SELECT name FROM attendees WHERE meeting_id=?", (meeting_id,)
        ).fetchall()]
        return {
            "tasks":     fetch("action_items"),
            "decisions": fetch("decisions"),
            "blockers":  fetch("blockers"),
            "ambiguous": fetch("ambiguous"),
            "attendees": attendees,
        }
    finally:
        conn.close()

def get_meeting_meta(meeting_id: str):
    conn = get_connection()

    try:
        row = conn.execute(
            """
            SELECT title, date
            FROM meetings
            WHERE id = ?
            """,
            (meeting_id,)
        ).fetchone()

        return dict(row) if row else None

    finally:
        conn.close()

def delete_meeting(meeting_id: str):
    """Delete a meeting and all its related records (CASCADE handles child rows)."""
    conn = get_connection()
    try:
        conn.execute("DELETE FROM meetings WHERE id=?", (meeting_id,))
        conn.commit()
    finally:
        conn.close()

def delete_multiple_meetings(meeting_ids: list[str]):
    conn = get_connection()

    try:
        for meeting_id in meeting_ids:
            conn.execute(
                "DELETE FROM meetings WHERE id=?",
                (meeting_id,)
            )

        conn.commit()

    finally:
        conn.close()

# ── Update functions ──────────────────────────────────────────────────────────

def update_tasks(rows: list[dict], meeting_id: str):
    conn = get_connection()
    try:
        for row in rows:
            conn.execute("""
                UPDATE action_items
                SET title=?, owner=?, due_date=?, priority=?, status=?, note=?
                WHERE id=? AND meeting_id=?
            """, (row.get("title"), row.get("owner"), row.get("due_date"),
                  row.get("priority"), row.get("status"), row.get("note"),
                  row["id"], meeting_id))
        conn.commit()
    finally:
        conn.close()


def update_blockers(rows: list[dict], meeting_id: str):
    conn = get_connection()
    try:
        for row in rows:
            conn.execute("""
                UPDATE blockers SET task=?, blocked_by=?, owner=?, ticket=?
                WHERE id=? AND meeting_id=?
            """, (row.get("task"), row.get("blocked_by"),
                  row.get("owner"), row.get("ticket"),
                  row["id"], meeting_id))
        conn.commit()
    finally:
        conn.close()


def update_decisions(rows: list[dict], meeting_id: str):
    conn = get_connection()
    try:
        for row in rows:
            conn.execute("""
                UPDATE decisions SET decision=?, rationale=?, status=?, note=?
                WHERE id=? AND meeting_id=?
            """, (row.get("decision"), row.get("rationale"),
                  row.get("status"), row.get("note"),
                  row["id"], meeting_id))
        conn.commit()
    finally:
        conn.close()


def update_ambiguous(rows: list[dict], meeting_id: str):
    conn = get_connection()
    try:
        for row in rows:
            conn.execute("""
                UPDATE ambiguous SET description=?, owner=?, note=?
                WHERE id=? AND meeting_id=?
            """, (row.get("description"), row.get("owner"), row.get("note"),
                  row["id"], meeting_id))
        conn.commit()
    finally:
        conn.close()


# ── Insert functions — IDs scoped to meeting ─────────────────────────────────
# IDs are prefixed with a short meeting hash so they never collide across meetings
# Display numbers shown in UI are always 1-based per meeting

def _next_id(conn, table: str, prefix: str, meeting_id: str) -> str:
    """Generate next sequential ID scoped to this meeting."""
    row = conn.execute(
        f"SELECT COUNT(*) as cnt FROM {table} WHERE meeting_id=?",
        (meeting_id,)
    ).fetchone()
    n = (row["cnt"] if row else 0) + 1
    # Use meeting suffix + sequence to guarantee global uniqueness
    m_suffix = meeting_id[-6:].replace("-", "")
    return f"{prefix}_{m_suffix}_{n:03d}"


def insert_task(meeting_id: str):
    conn = get_connection()
    try:
        new_id = _next_id(conn, "action_items", "task", meeting_id)
        conn.execute("""
            INSERT INTO action_items (id, meeting_id, title, owner, due_date, priority, status, note)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (new_id, meeting_id, "New task", None, None, "medium", "open", None))
        conn.commit()
    finally:
        conn.close()


def insert_blocker(meeting_id: str):
    conn = get_connection()
    try:
        new_id = _next_id(conn, "blockers", "blk", meeting_id)
        conn.execute("""
            INSERT INTO blockers (id, meeting_id, task, blocked_by, owner, ticket)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (new_id, meeting_id, "Blocked task", "Reason for block", None, None))
        conn.commit()
    finally:
        conn.close()


def insert_decision(meeting_id: str):
    conn = get_connection()
    try:
        new_id = _next_id(conn, "decisions", "dec", meeting_id)
        conn.execute("""
            INSERT INTO decisions (id, meeting_id, decision, rationale, status, note)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (new_id, meeting_id, "New decision", None, "pending", None))
        conn.commit()
    finally:
        conn.close()


def insert_ambiguous(meeting_id: str):
    conn = get_connection()
    try:
        new_id = _next_id(conn, "ambiguous", "amb", meeting_id)
        conn.execute("""
            INSERT INTO ambiguous (id, meeting_id, description, owner, note)
            VALUES (?, ?, ?, ?, ?)
        """, (new_id, meeting_id, "Describe ambiguity", None, None))
        conn.commit()
    finally:
        conn.close()


def delete_row(table: str, row_id: str, meeting_id: str):
    """
    Delete a single row identified by BOTH id AND meeting_id.
    With composite PK (id, meeting_id), id alone is not unique across
    meetings — meeting_id is required to target the correct row.
    """
    conn = get_connection()
    try:
        conn.execute(
            f"DELETE FROM {table} WHERE id=? AND meeting_id=?",
            (row_id, meeting_id)
        )
        conn.commit()
    finally:
        conn.close()


# ════════════════════════════════════════════════════════
#  Pipeline
# ════════════════════════════════════════════════════════

def run_pipeline(txt_content: str) -> tuple[bool, str]:
    try:
        raw_json   = llm_for_structured_json(txt_content)
        clean_json = clean_json_response(raw_json)
        data       = json.loads(clean_json)
        meeting_id = save_extraction(data)
        return True, meeting_id
    except json.JSONDecodeError as e:
        return False, f"JSON parse error: {e}"
    except Exception as e:
        return False, f"Pipeline error: {e}"


# ════════════════════════════════════════════════════════
#  Table renderers  — native widgets inside a styled box
# ════════════════════════════════════════════════════════

def _hdr(col, label: str):
    col.markdown(f'<div class="tbl-hdr">{label}</div>', unsafe_allow_html=True)


# def _id_cell(col, val: str):
#     col.markdown(f'<div class="tbl-id">{val}</div>', unsafe_allow_html=True)


def render_tasks_table(tasks: list[dict], meeting_id: str):
    # ── action bar ────────────────────────────────────────
    c1, c2, c3, c4 = st.columns([1, 1, 1.6, 1])
    with c1:
        if st.button("＋ Add Task", key="add_task"):
            insert_task(meeting_id)
            st.rerun()
    save_clicked = c2.button("💾 Save Tasks", key="save_tasks")

    if not tasks:
        st.info("No tasks yet. Click ＋ Add Task to create one.")
        return

    # Delete row selector
    with c3:
        del_opts = ["— select row to delete —"] + [
            f"#{i+1} {t.get('title','')[:35]}" for i, t in enumerate(tasks)]
        del_sel = st.selectbox("del", del_opts, key="del_task_sel", label_visibility="collapsed")
    with c4:
        if del_sel != "— select row to delete —" and st.button("🗑 Delete Row", key="del_task_btn"):
            idx = del_opts.index(del_sel) - 1
            delete_row("action_items", tasks[idx]["id"], meeting_id)
            st.rerun()

    st.markdown('<div style="height:6px"></div>', unsafe_allow_html=True)

    # ── header row ────────────────────────────────────────
    cols = [0.35, 2, 1, 1, 1, 1.0, 2.5]
    hdrs = st.columns(cols)
    for col, lbl in zip(hdrs, ["ID", "Task Title", "Owner", "Due Date", "Priority", "Status", "Note"]):
        _hdr(col, lbl)

    # ── data rows ─────────────────────────────────────────
    edited_rows = []
    for i, t in enumerate(tasks):
        c = st.columns(cols)
        # Row number (1-based, per meeting)
        c[0].markdown(f'<div class="tbl-id">{i+1}</div>', unsafe_allow_html=True)
        # _id_cell(c[1], t["id"].split("_")[-1])   # show only sequence number
        row = {"id": t["id"]}
        row["title"]    = c[1].text_area("Title", value=t.get("title")    or "", height=100, key=f"{meeting_id}_t_title_{i}", label_visibility="collapsed")
        row["owner"]    = c[2].text_input("Task Owner", value=t.get("owner")    or "", key=f"{meeting_id}_t_owner_{i}", label_visibility="collapsed")
        row["due_date"] = c[3].text_input("Due Date", value=t.get("due_date") or "", key=f"{meeting_id}_t_date_{i}",  label_visibility="collapsed")
        row["priority"] = c[4].selectbox("Pripority", ["high","medium","low"], index=["high","medium","low"].index(t.get("priority") or "medium"), key=f"{meeting_id}_t_pri_{i}", label_visibility="collapsed")
        row["status"]   = c[5].selectbox("Status", ["open","on_hold","blocked"], index=["open","on_hold","blocked"].index(t.get("status") or "open"), key=f"{meeting_id}_t_stat_{i}", label_visibility="collapsed")
        row["note"]     = c[6].text_area("Note", value=t.get("note")     or "", height=100, key=f"{meeting_id}_t_note_{i}",  label_visibility="collapsed")
        edited_rows.append(row)

        st.markdown(
            "<div style='height:8px'></div>",
            unsafe_allow_html=True)
        
    if save_clicked:
        update_tasks(edited_rows, meeting_id)
        st.success("Tasks saved.", icon="✅")
        st.rerun()


def render_blockers_table(blockers: list[dict], meeting_id: str):
    c1, c2, c3, c4 = st.columns([1, 1, 1.6, 1])
    with c1:
        if st.button("＋ Add Blocker", key="add_blk"):
            insert_blocker(meeting_id)
            st.rerun()
    save_clicked = c2.button("💾 Save Blockers", key="save_blk")

    if not blockers:
        st.info("No blockers recorded.")
        return

    with c3:
        del_opts = ["— select row to delete —"] + [
            f"#{i+1} {b.get('task','')[:35]}" for i, b in enumerate(blockers)
        ]
        del_sel = st.selectbox("del", del_opts, key="del_blk_sel", label_visibility="collapsed")
    with c4:
        if del_sel != "— select row to delete —" and st.button("🗑 Delete Row", key="del_blk_btn"):
            idx = del_opts.index(del_sel) - 1
            delete_row("blockers", blockers[idx]["id"], meeting_id)
            st.rerun()

    st.markdown('<div style="height:6px"></div>', unsafe_allow_html=True)

    cols = [0.35, 3.5, 3, 1.2, 1]
    hdrs = st.columns(cols)
    for col, lbl in zip(hdrs, ["ID", "Blocked Task", "Blocked By", "Resolver", "Ticket"]):
        _hdr(col, lbl)

    edited_rows = []
    for i, b in enumerate(blockers):
        c = st.columns(cols)
        c[0].markdown(f'<div class="tbl-id">{i+1}</div>', unsafe_allow_html=True)
        row = {"id": b["id"]}
        row["task"]       = c[1].text_area("Task", value=b.get("task")       or "",height=100, key=f"{meeting_id}_b_task_{i}", label_visibility="collapsed")
        row["blocked_by"] = c[2].text_area("Blocked By", value=b.get("blocked_by") or "",height=100, key=f"{meeting_id}_b_by_{i}",   label_visibility="collapsed")
        row["owner"]      = c[3].text_input("Task Owner", value=b.get("owner")      or "", key=f"{meeting_id}_b_own_{i}",  label_visibility="collapsed")
        row["ticket"]     = c[4].text_input("Ticket", value=b.get("ticket")     or "", key=f"{meeting_id}_b_tkt_{i}",  label_visibility="collapsed")
        edited_rows.append(row)

        st.markdown(
            "<div style='height:8px'></div>",
            unsafe_allow_html=True
        )
    if save_clicked:
        update_blockers(edited_rows, meeting_id)
        st.success("Blockers saved.", icon="✅")
        st.rerun()


def render_decisions_table(decisions: list[dict], meeting_id: str):
    c1, c2, c3, c4 = st.columns([1, 1, 1.6, 1])
    with c1:
        if st.button("＋ Add Decision", key="add_dec"):
            insert_decision(meeting_id)
            st.rerun()
    save_clicked = c2.button("💾 Save Decisions", key="save_dec")

    if not decisions:
        st.info("No decisions recorded.")
        return

    with c3:
        del_opts = ["— select row to delete —"] + [
            f"#{i+1} {d.get('decision','')[:35]}" for i, d in enumerate(decisions)
        ]
        del_sel = st.selectbox("del", del_opts, key="del_dec_sel", label_visibility="collapsed")
    with c4:
        if del_sel != "— select row to delete —" and st.button("🗑 Delete Row", key="del_dec_btn"):
            idx = del_opts.index(del_sel) - 1
            delete_row("decisions", decisions[idx]["id"], meeting_id)
            st.rerun()

    st.markdown('<div style="height:6px"></div>', unsafe_allow_html=True)

    cols = [0.35, 3.3, 3.5, 1.5, 2]
    hdrs = st.columns(cols)
    for col, lbl in zip(hdrs, ["ID", "Decision", "Rationale", "Status", "Note"]):
        _hdr(col, lbl)

    edited_rows = []
    for i, d in enumerate(decisions):
        c = st.columns(cols)
        c[0].markdown(f'<div class="tbl-id">{i+1}</div>', unsafe_allow_html=True)
        row = {"id": d["id"]}
        row["decision"]  = c[1].text_area("Decisions", value=d.get("decision")  or "", height=100, key=f"{meeting_id}_d_dec_{i}",  label_visibility="collapsed")
        row["rationale"] = c[2].text_area("Rationale", value=d.get("rationale") or "", height=100, key=f"{meeting_id}_d_rat_{i}",  label_visibility="collapsed")
        stat_opts = ["confirmed","deferred","pending"]
        row["status"] = c[3].selectbox("Status", stat_opts, index=stat_opts.index(d.get("status") or "pending"),
            key=f"{meeting_id}_d_stat_{i}", label_visibility="collapsed")
        row["note"]      = c[4].text_area("Note", value=d.get("note") or "", height=100, key=f"{meeting_id}_d_note_{i}", label_visibility="collapsed")
        edited_rows.append(row)
        
        st.markdown(
            "<div style='height:8px'></div>",
            unsafe_allow_html=True
        )
    if save_clicked:
        update_decisions(edited_rows, meeting_id)
        st.success("Decisions saved.", icon="✅")
        st.rerun()


def render_ambiguous_table(ambiguous: list[dict], meeting_id: str):
    c1, c2, c3, c4 = st.columns([1, 1, 1.6, 1])
    with c1:
        if st.button("＋ Add Item", key="add_amb"):
            insert_ambiguous(meeting_id)
            st.rerun()
    save_clicked = c2.button("💾 Save Ambiguous", key="save_amb")

    if not ambiguous:
        st.info("No ambiguous items recorded.")
        return

    with c3:
        del_opts = ["— select row to delete —"] + [
            f"#{i+1} {a.get('description','')[:35]}" for i, a in enumerate(ambiguous)
        ]
        del_sel = st.selectbox("del", del_opts, key="del_amb_sel", label_visibility="collapsed")
    with c4:
        if del_sel != "— select row to delete —" and st.button("🗑 Delete Row", key="del_amb_btn"):
            idx = del_opts.index(del_sel) - 1
            delete_row("ambiguous", ambiguous[idx]["id"], meeting_id)
            st.rerun()

    st.markdown('<div style="height:6px"></div>', unsafe_allow_html=True)

    cols = [0.35, 4, 1.2, 3]
    hdrs = st.columns(cols)
    for col, lbl in zip(hdrs, ["ID", "Description", "Owner", "Note"]):
        _hdr(col, lbl)

    edited_rows = []
    for i, a in enumerate(ambiguous):
        c = st.columns(cols)
        c[0].markdown(f'<div class="tbl-id">{i+1}</div>', unsafe_allow_html=True)
        row = {"id": a["id"]}
        row["description"] = c[1].text_area("Description", value=a.get("description") or "", height=100, key=f"{meeting_id}_a_desc_{i}", label_visibility="collapsed")
        row["owner"]       = c[2].text_input("Task Owner", value=a.get("owner") or "", key=f"{meeting_id}_a_own_{i}",  label_visibility="collapsed")
        row["note"]        = c[3].text_area("Note", value=a.get("note") or "", height=100, key=f"{meeting_id}_a_note_{i}", label_visibility="collapsed")
        edited_rows.append(row)
        
        st.markdown(
            "<div style='height:8px'></div>",
            unsafe_allow_html=True
        )
    if save_clicked:
        update_ambiguous(edited_rows, meeting_id)
        st.success("Ambiguous items saved.", icon="✅")
        st.rerun()


# ════════════════════════════════════════════════════════
#  Main
# ════════════════════════════════════════════════════════

def main():
    initialise_db()

    st.markdown("""
    <div class="hero">
        <h1 class="hero-title">Intelligence <em>Meeting Bot</em></h1>
        <p class="hero-sub">Upload a transcript &nbsp;·&nbsp; Extract structure &nbsp;·&nbsp; Edit &amp; track</p>
        <div class="divider-line"></div>
    </div>
    """, unsafe_allow_html=True)

    left, right = st.columns([1, 3.5], gap="large")

    # ── LEFT panel ────────────────────────────────────────────────────────────
    with left:
        st.markdown('<div class="sec-label">📂 Upload Transcript</div>', unsafe_allow_html=True)

        uploaded = st.file_uploader("txt", type=["txt"], label_visibility="collapsed")

        if uploaded:
            st.markdown(
                f'<div style="background:var(--bg-soft);border:1.5px solid var(--border);'
                f'border-radius:8px;padding:0.6rem 1rem;font-size:0.83rem;color:var(--text-dark);margin-bottom:0.8rem;">'
                f'📄 <strong>{uploaded.name}</strong><br>'
                f'<span style="color:var(--text-soft);">{uploaded.size/1024:.1f} KB</span></div>',
                unsafe_allow_html=True,
            )
            if st.button("⚡  Extract & Store", key="extract_btn"):
                content  = uploaded.getvalue().decode("utf-8")
                steps_ph = st.empty()

                def show_steps(stage: int):
                    labels = ["Reading transcript","Calling LLM","Parsing JSON","Saving to database"]
                    html = ""
                    for i, lbl in enumerate(labels):
                        if i < stage:   cls, icon = "p-done",    "✓"
                        elif i == stage: cls, icon = "p-running", "⟳"
                        else:            cls, icon = "p-wait",    "○"
                        html += f'<div class="p-step {cls}">{icon} {lbl}</div>'
                    steps_ph.markdown(html, unsafe_allow_html=True)

                for s in range(3):
                    show_steps(s); time.sleep(0.25)

                success, result = run_pipeline(content)
                if success:
                    show_steps(4)
                    st.success(f"Stored as `{result}`", icon="✅")
                    st.session_state["active_meeting"] = result
                    load_meetings.clear()
                    st.rerun()
                else:
                    steps_ph.empty()
                    st.error(result)

        st.markdown("<hr>", unsafe_allow_html=True)
        st.markdown('<div class="sec-label">🗂 Past Meetings</div>', unsafe_allow_html=True)

        meetings = load_meetings()
        if not meetings:
            st.markdown(
                '<p style="color:var(--text-soft);font-style:italic;font-size:0.82rem;">No meetings stored yet.</p>',
                unsafe_allow_html=True,
            )
        else:
            options = {f"{m['date']} — {m['title'] or m['id']}": m["id"] for m in meetings}
            active_id    = st.session_state.get("active_meeting")
            ids          = list(options.values())
            default_idx  = ids.index(active_id) if active_id in ids else 0

            chosen = st.selectbox("meeting", list(options.keys()),
                                  index=default_idx, label_visibility="collapsed")
            if chosen:
                st.session_state["active_meeting"] = options[chosen]

        # ── Delete meeting ─────────────────────────────────────────────────
        if meetings:
            st.markdown("<hr>", unsafe_allow_html=True)
            st.markdown(
                """
                <div class="danger-zone">
                    <div style="font-weight:700;color:#8B1A1A;">
                        ⚠ Meeting Management
                    </div>
                    <div style="font-size:0.8rem;">
                        Select one or more meetings to permanently remove.
                    </div>
                </div>
                """,
                unsafe_allow_html=True)

            meeting_lookup = {
                f"{m['date']} — {m['title'] or m['id']}": m["id"]
                for m in meetings}

            meetings_to_delete = st.multiselect(
                "Select meetings to delete",
                options=list(meeting_lookup.keys()))
            
            confirm_delete = st.checkbox(
                "I understand these meetings cannot be recovered")
            if meetings_to_delete and confirm_delete:
                if st.button("🗑 Delete Selected Meetings"):
                    delete_multiple_meetings(
                        [
                            meeting_lookup[m]
                            for m in meetings_to_delete
                        ])

                    load_meetings.clear()
                    if (st.session_state.get("active_meeting") in
                        [meeting_lookup[m] for m in meetings_to_delete]):
                        st.session_state.pop(
                            "active_meeting",
                            None)
                    st.success(
                        f"Deleted {len(meetings_to_delete)} meetings")
                    st.rerun()

    # ── RIGHT panel ───────────────────────────────────────────────────────────
    with right:
        meeting_id = st.session_state.get("active_meeting")

        if not meeting_id:
            st.markdown("""
            <div style="display:flex;flex-direction:column;align-items:center;justify-content:center;
                        height:380px;background:var(--bg-card);border:1.5px dashed var(--border);
                        border-radius:16px;opacity:0.7;">
                <div style="font-size:3.5rem;">🎙️</div>
                <div style="font-family:'DM Serif Display',serif;font-size:1.3rem;margin-top:0.8rem;color:var(--wine);">
                    Upload a transcript to begin</div>
                <div style="font-size:0.82rem;margin-top:0.4rem;color:var(--text-soft);">
                    Editable tables will appear here</div>
            </div>
            """, unsafe_allow_html=True)
            return

        data = load_meeting_data(meeting_id)
        meeting_meta = get_meeting_meta(meeting_id)
        
        # Stat strip

        if meeting_meta:
            title = meeting_meta["title"]
            date = meeting_meta["date"]
            st.markdown(
                f"""
                <h1 style="
                    margin-bottom:0;
                    color:#450920;
                    font-family:'DM Serif Display', serif;
                ">
                    {title}
                </h1>
                
                <div style="color: var(--text-soft); font-size: 0.9rem; margin-top: 0.2rem;"> 
                📅 {date}
                </div>""",
                unsafe_allow_html=True
            )
        
        st.markdown(f"""
        <div class="stat-row">
            <div class="stat-box"><div class="stat-num">{len(data["tasks"])}</div><div class="stat-lbl">Tasks</div></div>
            <div class="stat-box"><div class="stat-num">{len(data["blockers"])}</div><div class="stat-lbl">Blockers</div></div>
            <div class="stat-box"><div class="stat-num">{len(data["decisions"])}</div><div class="stat-lbl">Decisions</div></div>
            <div class="stat-box"><div class="stat-num">{len(data["ambiguous"])}</div><div class="stat-lbl">Ambiguous</div></div>
        </div>
        """, unsafe_allow_html=True)

        # Attendee pills
        if data["attendees"]:
            pills = "".join(f'<span class="att-pill">{n}</span>' for n in data["attendees"])
            st.markdown(f'<div style="margin-bottom:1rem;">{pills}</div>', unsafe_allow_html=True)

        # ── Stacked expanders — tables fully inside each box ──────────────
        with st.expander(f"📋  Tasks  ({len(data['tasks'])})", expanded=True):
            st.markdown(
                '<p style="font-size:0.78rem;color:#9C6B52;margin:0 0 0.6rem;">Edit any field. '
                'Use dropdowns for Priority / Status. Click Save Tasks to persist.</p>',
                unsafe_allow_html=True)
            render_tasks_table(data["tasks"], meeting_id)

        st.markdown('<div style="height:0.4rem"></div>', unsafe_allow_html=True)

        with st.expander(f"🚧  Blockers  ({len(data['blockers'])})", expanded=True):
            st.markdown(
                '<p style="font-size:0.78rem;color:#9C6B52;margin:0 0 0.6rem;">Edit blocker details. '
                'Click Save Blockers to persist.</p>',
                unsafe_allow_html=True)
            render_blockers_table(data["blockers"], meeting_id)

        st.markdown('<div style="height:0.4rem"></div>', unsafe_allow_html=True)

        with st.expander(f"✅  Decisions  ({len(data['decisions'])})", expanded=True):
            st.markdown(
                '<p style="font-size:0.78rem;color:#9C6B52;margin:0 0 0.6rem;">Edit decisions and '
                'update their status. Click Save Decisions to persist.</p>',
                unsafe_allow_html=True)
            render_decisions_table(data["decisions"], meeting_id)

        st.markdown('<div style="height:0.4rem"></div>', unsafe_allow_html=True)

        with st.expander(f"❓  Ambiguous  ({len(data['ambiguous'])})", expanded=True):
            st.markdown(
                '<p style="font-size:0.78rem;color:#9C6B52;margin:0 0 0.6rem;">Clarify or remove '
                'ambiguous items once resolved.</p>',
                unsafe_allow_html=True)
            render_ambiguous_table(data["ambiguous"], meeting_id)

        st.markdown("<hr>", unsafe_allow_html=True)
        st.markdown('<div class="sec-label">📧 Send Notifications</div>',
                    unsafe_allow_html=True)
        st.markdown(
            '<p style="font-size:0.78rem;color:#9C6B52;">Send a personalised email digest '
            'to every owner in this meeting.</p>',
            unsafe_allow_html=True)

        col_dry, col_send = st.columns(2)
        with col_dry:
            if st.button("👁 Preview Recipients", key="notif_preview"):
                result = notify_meeting(meeting_id, dry_run=True)
                for r in result.get("recipients", []):
                    st.write(f"→ {r['name']} — {r['email']}")

        with col_send:
            if st.button("📧 Send All Notifications", key="notif_send"):
                with st.spinner("Sending emails..."):
                    result = notify_meeting(meeting_id, dry_run=False)
                if result["failed"] == 0:
                    st.success(f"✅ Sent {result['sent']} emails successfully.")
                else:
                    st.warning(
                        f"Sent {result['sent']}, failed {result['failed']}: "
                        f"{', '.join(result['failures'])}"
                    )
if __name__ == "__main__":
    main()