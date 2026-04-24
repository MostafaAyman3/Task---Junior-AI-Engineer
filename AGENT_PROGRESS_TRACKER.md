# Agent Progress Tracker

## Objective
Build a from-scratch, production-ready Conversational AI Assistant interacting with `Real Estate Listings.xlsx` and `Marketing Campaigns.xlsx` using pure Python (no AI frameworks) and supporting bilingual capabilities (English/Arabic) with LLM routing (gpt-oss-120b fallback to gemini-3-flash).

## Current Status: ALL STEPS COMPLETE. Ready to Ship!
**Current Action:** Finished Step 5 & Step 6. 

### Step 1: Initialization
- [x] Create project folder structure (`agent/`, `tools/`, `data/`, `utils/`, `prompts/`, `tests/`).
- [x] Create `.env.example` with API key placeholders.
- [x] Create `requirements.txt` with required dependencies via Pandas.
- [x] Create `AGENT_PROGRESS_TRACKER.md`.

### Step 2: Data Layer (`utils/excel_io.py`, `data/store.py`, `utils/validator.py`)
- [x] Implement Excel loading/saving.
- [x] Apply date serial conversions safely (coerce errors).
- [x] Calculate computed columns (ROI, CTR, CPC, CPR).
- [x] Handle missing/empty data fields.

### Step 3: Tooling Layer (`tools/*.py`)
- [x] Implement core tools: `read`, `query`, `insert`, `update`, `delete`, `aggregate`, `describe`, `get_by_id`.
- [x] Apply String ID generation logic (`LST-XXXX`, `CMP-XXXX`).
- [x] Add empty DataFrame protection during insert logic.
- [x] Add state mapping handling in query mask logic.
- [x] Handle NaN correctly in Pandas calculations/serializations.
- [x] Add destructive action guards (`confirm: bool`) during update/delete tools.

### Step 4: The Agent Core (`agent/agent.py`, `utils/llm_client.py`)
- [x] Build LLM client with `gpt-oss-120b` -> `gemini-3-flash` fallback logic (`utils/llm_client.py`).
- [x] Inject structured prompts exact schema and tool specs (`agent/prompt_builder.py`).
- [x] Enforce output validations to valid JSON and clean Markdown blocks.
- [x] Ensure conversational history is passed to LLM (up to 12 turns max bounded).
- [x] Built the Agent execution loop supporting `single`, `multi`, `clarify`, and `answer`.

### Step 5: The Interface (`main.py`)
- [x] Build the CLI REPL loop with proper startup (`DataStore.initialize()`).
- [x] Implement graceful exit handlers (quit, exit, Ctrl+C).
- [x] Print standardized, highly visible terminal outputs.

### Step 6: GitHub Deliverables
- [x] Produce `<root>/README.md`.
- [x] Produce `<root>/DECISIONS.md` rigorously defending architectural design (No Frameworks, Pandas vs SQL, LLM routing, JSON tools over `exec()`).

## Known Bugs / Tweaks Handled
- **Data Type Coercion Bug:** Resolved `TypeError: '>' not supported between instances of 'datetime.date' and 'str'` by building a universal `coerce_value()` helper in `utils/validator.py`. It dynamically checks `df.dtype` or `datetime.date` types and casts incoming string inputs into proper Py objects inside `query`, `update`, and `insert` operations.
- **Pandas Date Parsing Bug:** Fixed `openpyxl` automatic datetime detection in `excel_io.py` (removed manual 25569 Unix epoch subtraction which caused TypeErrors in modern pandas versions).
- **LLM SDK Integration:** Replaced raw `requests` mock endpoints with official `openai` (for Groq) and `google-genai` (for Gemini) Python SDKs for production stability.
- **Advanced Fallback Chain:** Upgraded `llm_client.py` to handle dynamic multi-model degradation (e.g., trying `openai/gpt-oss-20b`, then falling back to a chain of multiple Gemini models like `gemini-3-flash-preview` -> `gemini-3.1-flash-lite-preview` -> `gemini-2.5-flash-lite` -> `gemini-1.5-flash`).
- **Context Window Management:** Bounded the `conversation_history` to exactly 12 interactions in `agent.py` to prevent `413 Payload Too Large` errors from the LLM endpoint.
- **Native Tool-Calling Interception:** Fixed `400 Bad Request` exceptions on Groq by explicitly enforcing `"response_format": {"type": "json_object"}`.
- **Strict Language Enforcements:** Updated `system_prompt.txt` to strictly ban hallucinated languages (e.g., Persian/Farsi) and enforce correct bilingual output (Arabic/English).