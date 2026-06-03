import sys
from pathlib import Path

# Ensure project root is on sys.path when running the file directly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import json
import logging
from app.pipeline.transcript_preprocessor import preprocess
from app.pipeline.llm_call import llm_for_structured_json
from app.pipeline.validator import clean_json_response
from app.db.db_schema import initialise_db, check_db_health
from app.db.db_writer import save_extraction

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

if len(sys.argv) >= 2:
    vtt_file = sys.argv[1]
else:
    vtt_file = "data/sprint_planning_incomplete_fields.vtt"

# Stage 1: initialise the database
initialise_db()

# Stage 2: preprocess the VTT into clean text
structured_text = preprocess(vtt_file)

# Stage 3: send to LLM
raw_json = llm_for_structured_json(structured_text)

# Stage 4: strip any markdown fences
clean_json = clean_json_response(raw_json)

# Stage 5: parse and insert into the database
data = json.loads(clean_json)
save_extraction(data)

# Summary
print("\nDatabase health check:")
health = check_db_health()
for table, count in health.items():
    print(f"  {table:<20} {count} rows")
