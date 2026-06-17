# 🎙️ Meeting Intelligence Bot

An AI-powered meeting analysis platform that transforms unstructured meeting transcripts into actionable business intelligence.

**Live Demo:** https://meeting-intelligent-bot.streamlit.app/

---

## Overview

Meeting Intelligence Bot automates the entire post-meeting workflow by extracting structured insights from meeting transcripts using Large Language Models (LLMs).

Instead of manually reviewing lengthy transcripts, users can upload meeting notes and instantly generate:

* Action Items
* Decisions Taken
* Blockers
* Ambiguous Items Requiring Clarification
* Ownership Assignments
* Due Dates
* Notification Emails

The platform stores extracted information in a structured database and automatically generates personalized notifications for meeting participants.

---

## Key Features

### AI-Powered Meeting Analysis

* Uses Google Gemini LLM for structured information extraction
* Converts raw meeting transcripts into machine-readable JSON
* Extracts tasks, decisions, blockers, and follow-up items

### Intelligent Action Item Tracking

* Identifies task owners
* Extracts deadlines
* Detects missing information
* Tracks task status

### Automated Notifications

* Personalized email digests
* Meeting-specific reminders
* Assignment notifications
* Deadline tracking

### Structured Data Storage

* SQLite-based storage layer
* Meeting history tracking
* Queryable records
* Persistent action item management

### Evaluation Framework

* Automated JSON quality validation
* Ground-truth comparison support
* Extraction accuracy assessment
* LLM output evaluation

### Modern Streamlit Dashboard

* Interactive transcript upload
* Structured results visualization
* Meeting analytics dashboard
* Downloadable outputs

---

## Architecture

```text
Meeting Transcript
        │
        ▼
Transcript Preprocessor
        │
        ▼
Google Gemini LLM
        │
        ▼
Structured JSON Extraction
        │
        ▼
JSON Validation Layer
        │
        ▼
SQLite Database
        │
        ├────────► Notification Engine
        │                    │
        │                    ▼
        │              Gmail API
        │
        ▼
Streamlit Dashboard
```

---

## Tech Stack

### AI & LLM

* Google Gemini
* Prompt Engineering
* Structured Output Generation

### Backend

* Python
* FastAPI-ready Architecture
* SQLite

### Frontend

* Streamlit

### Data Processing

* Pandas
* JSON Validation
* Regex-Based Transcript Processing

### Notifications

* Gmail API
* OAuth Authentication

### Evaluation

* DeepEval
* MLflow

### Deployment

* Streamlit Cloud

---

## Project Structure

```text
Meeting-Intelligent-Bot/
│
├── app.py
│
├── app/
│   ├── pipeline/
│   │   ├── transcript_preprocessor.py
│   │   ├── llm_call.py
│   │   └── validator.py
│   │
│   ├── db/
│   │   ├── db_schema.py
│   │   └── db_writer.py
│   │
│   ├── notifications/
│   │   ├── notification_engine.py
│   │   ├── gmail_client.py
│   │   └── email_builder.py
│   │
│   ├── orchestrator/
│   │   └── main.py
│   │
│   └── evaluation/
│       ├── evaluation.py
│       └── generate_json.py
│
└── requirements.txt
```

---

## Workflow

### Step 1

Upload a meeting transcript.

### Step 2

Transcript is cleaned and preprocessed.

### Step 3

Google Gemini extracts structured information.

### Step 4

The extracted JSON is validated.

### Step 5

Meeting insights are stored in SQLite.

### Step 6

Personalized notifications are generated and sent.

### Step 7

Results are displayed through the Streamlit dashboard.

---

## Example Outputs

### Action Items

```json
{
  "id": "task_001",
  "title": "Prepare sprint planning document",
  "owner": "Rishabh Sharma",
  "due_date": "2026-06-10",
  "priority": "high",
  "status": "open"
}
```

### Decision

```json
{
  "id": "dec_001",
  "decision": "Frontend release will be moved to next sprint",
  "status": "confirmed"
}
```

### Blocker

```json
{
  "id": "blk_001",
  "task": "API Integration",
  "blocked_by": "Pending client credentials"
}
```

---

## Installation

```bash
git clone https://github.com/<username>/Meeting-Intelligent-Bot.git

cd Meeting-Intelligent-Bot

pip install -r requirements.txt
```

---

## Environment Variables

Create a `.env` file:

```env
API_KEY=your_gemini_api_key
API_MODEL=gemini-model-name

GMAIL_CLIENT_ID=your_client_id
GMAIL_CLIENT_SECRET=your_client_secret
GMAIL_REFRESH_TOKEN=your_refresh_token
```

---

## Running Locally

```bash
streamlit run app.py
```

---

## Future Enhancements

* Microsoft Teams Integration
* Zoom Integration
* Google Meet API Integration
* ClickUp Task Creation
* Monday.com Integration
* Slack Notifications
* Vector Database Memory
* RAG-based Meeting Search
* Multi-Meeting Analytics Dashboard
* Role-Based Access Control

---

## Author

**Amreeta Surana**

AI/ML Engineer | Generative AI | LLM Applications | Data Science

LinkedIn: https://linkedin.com/in/AmreetaSurana

GitHub: https://github.com/AmreetaSurana
