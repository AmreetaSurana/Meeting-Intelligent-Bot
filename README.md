**Meeting Intelligence Agent**

**1\. Project Overview**

**1.1 Problem Statement**

Engineering and product teams conduct 10-20 meetings per week. Despite this, action items routinely go untracked, decisions made weeks ago are relitigated, and accountability gaps emerge because no structured record is maintained. Existing tools like Otter.ai, Fireflies, and Fathom provide transcription, but none automatically extract structured intelligence and push it into a task management system with automated follow-up.

**1.2 Solution**

The Meeting Intelligence Agent is an end-to-end pipeline that ingests raw Google Meet transcripts, uses a Large Language Model to extract structured tasks, decisions, blockers, and ambiguous items, pushes them automatically to ClickUp/Monday.com, logs them in a local database, and runs a scheduled notification engine that sends contextual emails for assignments, approaching deadlines, and overdue tasks. An LLM evaluation layer measures extraction quality, attribution accuracy, and RAG faithfulness across every run.

**1.3 Core Value Propositions**

- Zero manual effort : transcript upload triggers the entire pipeline automatically
- Structured intelligence : four categories extracted (tasks, decisions, blockers, ambiguous) not just a summary
- Contextual notifications : emails include the original meeting context, not just a generic reminder
- Queryable history : past meeting decisions searchable via natural language over Chroma vector index (optional)
- Measurable quality : extraction precision, attribution accuracy, and RAG faithfulness scored on every run

**2\. Technical Architecture & Pipeline**

**2.1 Technology Stack**

| **Component**       | **Technology**                                  | **Purpose**                                            |
| ------------------- | ----------------------------------------------- | ------------------------------------------------------ |
| Transcript Input    | Google Meet .vtt / .txt export, Fathom, Whisper | Source of raw meeting transcript                       |
| ---                 | ---                                             | ---                                                    |
| Pre-processing      | Python (regex module)                           | Strip timestamps, group by speaker, format text        |
| ---                 | ---                                             | ---                                                    |
| LLM Extraction      | Azure OpenAI GPT-4o                             | Extract structured JSON from cleaned transcript        |
| ---                 | ---                                             | ---                                                    |
| JSON Validation     | Python json + datetime                          | Enforce schema, fix missing fields and bad dates       |
| ---                 | ---                                             | ---                                                    |
| Task Board          | ClickUp/Monday.com REST API v2                  | Create tasks with assignees, due dates, priorities     |
| ---                 | ---                                             | ---                                                    |
| Structured Storage  | SQLite                                          | Store tasks, due dates, status, notification log       |
| ---                 | ---                                             | ---                                                    |
| Transcript Memory   | Chroma (vector DB)                              | Embed transcript chunks for contextual email retrieval |
| ---                 | ---                                             | ---                                                    |
| Email Notifications | Gmail API (OAuth2)                              | Send assignment, reminder, and overdue emails          |
| ---                 | ---                                             | ---                                                    |
| Email Scheduling    | APScheduler (cron)                              | Daily deadline and overdue detection at 11 AM          |
| ---                 | ---                                             | ---                                                    |
| Evaluation          | DeepEval, RAGAS, MLflow                         | Score extraction quality and RAG faithfulness          |
| ---                 | ---                                             | ---                                                    |

**2.2 End-to-End Pipeline (7 Stages)**

**Stage 1 - Transcript Input:** Accepts .vtt or .txt from Google Meet. Whisper provides audio-to-text fallback. All inputs normalised to plain text.

**Stage 2 - Pre-Processing:** Python re module strips timestamps and cue numbers, groups consecutive lines by speaker, and formats clean \[Speaker\]: text output for the LLM.

**Stage 3 - LLM Extraction:** Cleaned transcript sent to GPT-4o with a fixed system prompt. Model returns only valid JSON - no markdown, no explanation. Same prompt on every transcript ensures deterministic, evaluable output.

**Stage 4 - JSON Validation:** Output validated with Python json + datetime. Missing fields default to Unassigned / medium / null. Malformed dates reset to null. All downstream consumers receive a schema-compliant object**.**

**Stage 5 - Parallel Storage Routing:** Validated JSON routed simultaneously to ClickUp/Monday.com API (task creation), SQLite (deadline scheduling), Chroma (optional transcript embedding), and Gmail API (immediate assignment email).

**Stage 6 - Notification Engine:** APScheduler cron runs daily at 11 AM. Queries SQLite for tasks due in 1 day or overdue (excluding already-notified). LLM composes email body using SQLite fields and optional Chroma context. All sent emails logged to prevent duplicates.

**Stage 7 - LLM Evaluation:** Every run scored across four dimensions against ground-truth annotated test transcripts. Scores and config logged to MLflow for cross-run comparison.

**3\. Data Design**

**3.1 Extracted JSON Schema**

| **Field Group** | **Fields**                       | **Description**                            |
| --------------- | -------------------------------- | ------------------------------------------ |
| action_items    | title, owner, due_date, priority | Tasks explicitly assigned to a team member |
| ---             | ---                              | ---                                        |
| decisions       | decision, rationale              | Outcomes agreed upon during the meeting    |
| ---             | ---                              | ---                                        |
| blockers        | task, blocked_by, owner          | Tasks dependent on another unfinished item |
| ---             | ---                              | ---                                        |
| ambiguous       | description, owner: null         | Work discussed but no clear owner assigned |
| ---             | ---                              | ---                                        |

**3.2 ClickUp/Monday.com API Fields Mapped**

| **ClickUp/Monday.com API Field** | **Source in JSON**             | **Notes**                                                |
| -------------------------------- | ------------------------------ | -------------------------------------------------------- |
| name                             | action_items\[\].title         | Task title as extracted                                  |
| ---                              | ---                            | ---                                                      |
| assignees\[\]                    | action_items\[\].owner         | Mapped to ClickUp/Monday.com user ID via member registry |
| ---                              | ---                            | ---                                                      |
| due_date (Unix ms)               | action_items\[\].due_date      | Converted from YYYY-MM-DD to milliseconds                |
| ---                              | ---                            | ---                                                      |
| priority (1-3)                   | action_items\[\].priority      | high=1, medium=2, low=3                                  |
| ---                              | ---                            | ---                                                      |
| markdown_description             | Generated from meeting context | Includes meeting date and relevant transcript except     |
| ---                              | ---                            | ---                                                      |
| tags\[\]                         | Static: meeting-extracted      | Identifies all auto-created tasks                        |
| ---                              | ---                            | ---                                                      |
| links_to (dependency)            | blockers\[\].blocked_by        | Created via POST /task/{id}/dependency                   |
| ---                              | ---                            | ---                                                      |

**3.3 SQLite Schema (tasks table)**

CREATE TABLE tasks (id INTEGER PRIMARY KEY, title TEXT, owner TEXT, assignee_email TEXT, due_date TEXT, priority TEXT, status TEXT DEFAULT 'open', source_meeting TEXT, last_notified TEXT);

**3.4 Chroma Collection Design (Optional)**

- Collection: meeting_transcripts · Embedding: text-embedding-3-small (1536 dims)
- Documents: transcript chunks grouped by speaker turn, tagged with meeting_date and task_id
- Index: HNSW (auto-built by Chroma) - sub-10ms semantic query at any scale
- Purpose: contextual retrieval for email composer only - not used for task lookup

**4\. Notification Engine**

| **Email Type**    | **Trigger**                             | **Data Source**         | **Content**                                  |
| ----------------- | --------------------------------------- | ----------------------- | -------------------------------------------- |
| Assignment        | Immediately after extraction            | SQLite + Chroma context | Task title, owner, due date, meeting context |
| ---               | ---                                     | ---                     | ---                                          |
| Deadline reminder | 3 days before and 1 day before due date | SQLite + Chroma context | Task, deadline, original assignment context  |
| ---               | ---                                     | ---                     | ---                                          |
| Overdue alert     | due_date < today, once daily            | SQLite only             | Task, days overdue, escalation note          |
| ---               | ---                                     | ---                     | ---                                          |

Assignment and deadline reminder emails are LLM-composed using task fields from SQLite and the most relevant transcript chunk from Chroma (optional). Overdue alerts use SQLite only. All notifications logged to notification_log to prevent duplicate sends.

**5\. LLM Evaluation Layer**

| **Eval Type**       | **Tool**     | **Metric**              | **What it measures**                              |
| ------------------- | ------------ | ----------------------- | ------------------------------------------------- |
| Extraction eval     | DeepEval     | Precision / Recall / F1 | Did the LLM capture all tasks correctly?          |
| ---                 | ---          | ---                     | ---                                               |
| Attribution eval    | LLM-as-judge | Correct owner %         | Was the right person assigned to each task?       |
| ---                 | ---          | ---                     | ---                                               |
| RAG faithfulness    | RAGAS        | Faithfulness score      | Is the email context grounded in the transcript?  |
| ---                 | ---          | ---                     | ---                                               |
| Experiment tracking | MLflow       | Run comparison          | Compare extraction quality across prompt versions |
| ---                 | ---          | ---                     | ---                                               |

Ground truth: 10-15 annotated test transcripts with reference JSON (expected tasks, decisions, owners) created before evaluation. Extraction agent output compared against reference using precision, recall, and F1. LLM-as-judge scores owner attribution (0-1) with rationale, logged to MLflow. RAGAS faithfulness score below 0.65 triggers a flag in the output.

**6\. Limitations & Production Upgrade Path**

**Known Limitations**

- Unnamed speakers in transcript appear as 'Unassigned' - Google Meet must label speakers
- Relative due dates ('next Friday') reset to null by the JSON validator
- SQLite and Chroma (in-process) do not support concurrent multi-user write access

**Production Upgrade Path**

- Replace SQLite + Chroma with PostgreSQL + pgvector - one database for structured and semantic search
- Add Google Meet API to auto-fetch transcripts programmatically after each meeting
- Add Slack API notifications for teams that prefer in-channel alerts over email
- Add ClickUp/Monday.com webhook to sync task status changes back to local database in real time

