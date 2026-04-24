# System Design Document
## AI Assistant for Excel Data Management
### Junior AI Engineer — Senior Architecture Review

---

## TABLE OF CONTENTS

1. [System Overview](#1-system-overview)
2. [Architecture Design](#2-architecture-design)
3. [Agent Design](#3-agent-design)
4. [Tooling Layer](#4-tooling-layer)
5. [Data Handling Design](#5-data-handling-design)
6. [Function-Level Design](#6-function-level-design)
7. [End-to-End Flow Examples](#7-end-to-end-flow-examples)
8. [LLM Integration](#8-llm-integration)
9. [Error Handling & Robustness](#9-error-handling--robustness)
10. [Project Structure](#10-project-structure)
11. [Design Decisions & Tradeoffs](#11-design-decisions--tradeoffs)
12. [Open Questions](#12-open-questions)

---

## 1. SYSTEM OVERVIEW

### What the System Does

This system is a **conversational AI assistant** that enables users to interact with two Excel files — `real_estate_listings.xlsx` and `marketing_campaigns.xlsx` — using natural language. The user does not need to know anything about the data structure. They simply ask questions or issue commands ("Show me all listings above $500,000 in Texas", "Delete campaign ID 42", "Add a new listing..."), and the assistant interprets their intent, calls the right tool(s) with the right arguments, and returns a clear, human-readable answer.

### Key Capabilities

| Capability | Description |
|---|---|
| **Read / Query** | Filter, sort, aggregate, and summarize data from either file |
| **Insert** | Add new rows to either file, with validation |
| **Update / Modify** | Edit one or more fields in existing rows |
| **Delete** | Remove rows by ID or condition |
| **Cross-file awareness** | Understand which file a query targets |
| **Multi-step reasoning** | Chain multiple tool calls for complex requests |
| **Graceful error handling** | Surface clear errors when data is missing or invalid |

### User Interaction Flow

```
User types natural language query
        │
        ▼
[Agent: Intent Parser]  ←── Schema Context (column names, file names)
        │
        ▼
[Agent: Planner]  ──── Decides single-step or multi-step
        │
        ▼
[Agent: Tool Selector]  ──── Picks tool(s) and constructs arguments
        │
        ▼
[Tool Executor]  ──── Runs tool against in-memory DataFrame
        │
        ▼
[Agent: Response Synthesizer]  ──── Converts raw result to natural language
        │
        ▼
User receives clean, readable answer
```

---

## 2. ARCHITECTURE DESIGN

### High-Level Architecture

```
┌───────────────────────────────────────────────────────────┐
│                        CLI / Interface                     │
│                    (main.py – REPL loop)                   │
└──────────────────────────────┬────────────────────────────┘
                               │  user_input (str)
                               ▼
┌───────────────────────────────────────────────────────────┐
│                      AGENT CORE                            │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │   Planner   │→ │ Tool Selector│→ │    Executor      │  │
│  │(LLM call #1)│  │ (LLM call #1)│  │ (pure Python)    │  │
│  └─────────────┘  └──────────────┘  └──────────────────┘  │
│           ↑                                    │           │
│           │         [Conversation Memory]      │           │
│           └──────────── (in-process list) ─────┘           │
└──────────────────────────────┬────────────────────────────┘
                               │  tool_name + arguments
                               ▼
┌───────────────────────────────────────────────────────────┐
│                     TOOL REGISTRY                          │
│  read_data │ query_data │ insert_row │ update_row │ delete │
│  describe_schema │ aggregate_data │ sort_data              │
└──────────────────────────────┬────────────────────────────┘
                               │  operates on
                               ▼
┌───────────────────────────────────────────────────────────┐
│                   DATA STORE (in-memory)                   │
│    DataStore singleton                                     │
│    ├── real_estate_listings: pd.DataFrame                  │
│    └── marketing_campaigns:  pd.DataFrame                  │
│    + dirty flag per file → auto-save on mutation           │
└───────────────────────────────────────────────────────────┘
                               │  persists to
                               ▼
┌───────────────────────────────────────────────────────────┐
│                    EXCEL FILES (disk)                      │
│    /data/real_estate_listings.xlsx                         │
│    /data/marketing_campaigns.xlsx                          │
└───────────────────────────────────────────────────────────┘
```

### Components and Responsibilities

| Component | File(s) | Responsibility |
|---|---|---|
| **CLI Interface** | `main.py` | REPL loop, user I/O, session start/end |
| **Agent Core** | `agent/agent.py` | Orchestrates LLM calls, manages conversation |
| **Prompt Builder** | `agent/prompt_builder.py` | Assembles system + context + user prompt |
| **Tool Registry** | `agent/tool_registry.py` | Maps tool names → callable functions |
| **Individual Tools** | `tools/*.py` | One file per tool; pure deterministic Python |
| **Data Store** | `data/store.py` | Singleton holding loaded DataFrames |
| **Excel I/O** | `utils/excel_io.py` | load/save Excel with openpyxl/pandas |
| **Validator** | `utils/validator.py` | Schema validation for inserts/updates |
| **Response Formatter** | `utils/formatter.py` | Converts DataFrame/dict results → readable strings |
| **Logger** | `utils/logger.py` | Structured logging of every agent step |

### Why This Architecture

- **Separation of concerns**: The LLM only decides *what* to do; deterministic Python code *does* it. This makes the system testable, debuggable, and predictable.
- **No framework dependency**: The agent loop is a simple Python while-loop + JSON parsing — zero LangChain, zero abstraction magic.
- **In-memory DataStore**: Avoids repeated disk I/O on every query. A dirty-flag pattern ensures writes go back to disk only when data is mutated.
- **Tool Registry as a dictionary**: `{"query_data": query_data_fn, ...}` makes tool dispatch trivially simple and easy to extend.

---

## 3. AGENT DESIGN

### The Agent as a System

The agent is **not** a class that "thinks autonomously." It is a structured loop that:

1. Receives user input
2. Builds a prompt containing the schema, conversation history, available tools, and the user's message
3. Calls the LLM once to get a JSON tool-call decision
4. Dispatches that tool call to the Tool Registry
5. Optionally loops (for multi-step) or synthesizes a final response

### Sub-Systems

#### A. Planner

The Planner is **implicit inside the LLM prompt**. We instruct the LLM to think about whether the request requires one or multiple tool calls *before* outputting its decision. We do not build a separate planning step to keep the system simple and latency low.

For complex requests, the LLM outputs a `plan` field:

```json
{
  "plan": ["query_data to find listings in TX", "aggregate_data to get average price"],
  "steps": [
    {"tool": "query_data", "arguments": {...}},
    {"tool": "aggregate_data", "arguments": {...}}
  ]
}
```

The agent loop iterates through `steps` sequentially, feeding each tool result into the next step's context if needed.

#### B. Tool Selector

The LLM's output IS the tool selection. The prompt contains a strict JSON schema that the LLM must follow. The Tool Selector's role is:
- Parse the LLM's JSON response
- Validate that the tool name exists in the registry
- Validate that required arguments are present
- If validation fails → retry the LLM call once with an error correction prompt

#### C. Executor

Pure Python dispatcher:

```
tool_fn = TOOL_REGISTRY.get(tool_name)
if tool_fn is None:
    raise ToolNotFoundError(tool_name)
result = tool_fn(**arguments)
```

The Executor wraps every call in a try/except and returns a structured `ToolResult` object (success flag, data payload, error message).

#### D. Memory

**Short-term memory only** (this session). Implemented as a list of message dicts:

```python
conversation_history = [
    {"role": "user", "content": "Show listings in Texas"},
    {"role": "assistant", "content": "Found 12 listings..."},
    ...
]
```

This is injected into every LLM prompt (last N turns, configurable, default 6) to give the LLM conversational context. No vector DB, no persistent memory — this is by design for simplicity and because the task is session-scoped.

### How the Agent Decides Tool + Arguments

The decision-making is fully delegated to the LLM via a **structured output prompt**. Critically:

1. The system prompt includes the **full schema** of both Excel files (column names, data types, sample values).
2. The system prompt includes the **full tool catalog** with each tool's name, description, and argument schema.
3. The user message is appended.
4. The LLM is instructed to respond in a **strict JSON format only** — no prose.
5. The agent parses that JSON. If parsing fails, it sends a correction prompt.

### Multi-Step Query Handling

```
Agent loop pseudo-code:

response = llm_call(prompt)
parsed = parse_json(response)

if parsed.type == "single":
    result = execute_tool(parsed.tool, parsed.arguments)
    final_answer = llm_synthesize(result)

elif parsed.type == "multi":
    results = []
    for step in parsed.steps:
        step_result = execute_tool(step.tool, step.arguments)
        results.append(step_result)
        # inject prior results into next step if step.uses_previous == True
    final_answer = llm_synthesize(results)
```

---

## 4. TOOLING LAYER

All tools are pure functions: `(arguments) → ToolResult`. They operate on the DataStore singleton. They never call the LLM.

---

### Tool 1: `describe_schema`

**Purpose:** Returns column names, data types, and sample values for a given file. Used internally at startup and injected into every prompt. Can also be called by the agent if the user asks "what columns does this file have?"

**Input Schema:**
```json
{
  "file": "string  // 'real_estate' or 'marketing'"
}
```

**Output Schema:**
```json
{
  "success": true,
  "data": {
    "columns": [
      {"name": "price", "dtype": "float64", "sample": 450000.0},
      ...
    ],
    "row_count": 542
  }
}
```

**Internal Logic:**
1. Resolve `file` argument to the correct DataFrame from DataStore
2. For each column, extract: `col_name`, `df[col].dtype`, `df[col].dropna().iloc[0]` (first non-null sample)
3. Also return `len(df)` as `row_count`
4. Package and return as `ToolResult`

**Edge Cases:**
- Empty DataFrame → return columns but `row_count: 0`, no sample
- Unknown `file` value → return error immediately

---

### Tool 2: `read_data`

**Purpose:** Returns rows from a file, with optional limit. Used for "show me the data", "give me the first 10 listings", etc.

**Input Schema:**
```json
{
  "file": "string",
  "limit": "int | null  // default 10, max 100"
}
```

**Output Schema:**
```json
{
  "success": true,
  "data": {
    "rows": [ {...}, {...} ],
    "total_rows": 542,
    "returned_rows": 10
  }
}
```

**Internal Logic:**
1. Load DataFrame from DataStore
2. Apply `df.head(limit)` (cap limit at 100 to prevent huge responses)
3. Convert to list of dicts via `df.to_dict(orient="records")`
4. Return with total_rows = `len(df)`

**Edge Cases:**
- limit > 100 → silently cap to 100 and note it in the response
- Empty DataFrame → return empty rows list

---

### Tool 3: `query_data`

**Purpose:** Filter rows by one or more conditions. The most important tool. Handles "show me listings above $X in state Y with N bedrooms", etc.

**Input Schema:**
```json
{
  "file": "string",
  "filters": [
    {
      "column": "string",
      "operator": "string  // eq, ne, gt, gte, lt, lte, contains, startswith, in, not_in",
      "value": "any"
    }
  ],
  "columns": ["string"],
  "limit": "int | null"
}
```

**Output Schema:**
```json
{
  "success": true,
  "data": {
    "rows": [ {...} ],
    "matched_rows": 12,
    "total_rows": 542
  }
}
```

**Internal Logic:**
1. Load DataFrame from DataStore
2. Start with full DataFrame: `result = df.copy()`
3. For each filter in `filters`:
   - Resolve column: check if `filter.column` exists in `df.columns` (case-insensitive match)
   - Apply operator:
     - `eq` → `result = result[result[col] == value]`
     - `ne` → `result = result[result[col] != value]`
     - `gt` → `result = result[result[col] > value]`
     - `gte` → `result = result[result[col] >= value]`
     - `lt` → `result = result[result[col] < value]`
     - `lte` → `result = result[result[col] <= value]`
     - `contains` → `result = result[result[col].str.contains(value, case=False, na=False)]`
     - `startswith` → `result = result[result[col].str.startswith(value, na=False)]`
     - `in` → `result = result[result[col].isin(value)]` (value must be list)
     - `not_in` → `result = result[~result[col].isin(value)]`
4. If `columns` is provided, select only those columns
5. Apply `limit` (default 50)
6. Return matched_rows = `len(result)` (before limit), returned rows after limit

**Edge Cases:**
- Column not found → return error listing available columns
- Type mismatch (e.g., comparing string column with int) → attempt coercion, if fails return error
- No results → return empty rows with matched_rows: 0 (not an error)
- `in` with non-list value → wrap in list automatically

---

### Tool 4: `aggregate_data`

**Purpose:** Compute statistics — sum, mean, min, max, count, median — optionally grouped by a column.

**Input Schema:**
```json
{
  "file": "string",
  "column": "string",
  "operation": "string  // sum | mean | min | max | count | median | std",
  "group_by": "string | null",
  "filters": [ ... ]
}
```

**Output Schema:**
```json
{
  "success": true,
  "data": {
    "operation": "mean",
    "column": "price",
    "group_by": "state",
    "result": [
      {"state": "TX", "price_mean": 425000.0},
      ...
    ]
  }
}
```

**Internal Logic:**
1. Load DataFrame, apply any `filters` using the same logic as `query_data`
2. If `group_by` is provided:
   - `grouped = df.groupby(group_by)[column].agg(operation)`
   - Convert to list of dicts
3. If no `group_by`:
   - `result = getattr(df[column], operation)()`
   - Return as scalar value
4. Handle `count` specially: `df[column].count()` or `df.groupby(group_by)[column].count()`

**Edge Cases:**
- Operation on non-numeric column → return error if operation is sum/mean/etc.
- group_by column not found → return error
- All NaN column → return `null` result with a note

---

### Tool 5: `sort_data`

**Purpose:** Sort rows by one or more columns.

**Input Schema:**
```json
{
  "file": "string",
  "sort_by": [
    {"column": "string", "ascending": "bool  // default true"}
  ],
  "filters": [ ... ],
  "limit": "int | null"
}
```

**Output Schema:**
```json
{
  "success": true,
  "data": {
    "rows": [ {...} ],
    "total_rows": 542
  }
}
```

**Internal Logic:**
1. Load DataFrame, apply filters
2. Build columns list and ascending list from `sort_by`
3. `result = df.sort_values(by=columns, ascending=ascending_list)`
4. Apply limit, convert to records, return

**Edge Cases:**
- Sort column doesn't exist → return error
- Mixed types in column → pandas handles this; catch any exception and return error

---

### Tool 6: `insert_row`

**Purpose:** Add one new row to a file.

**Input Schema:**
```json
{
  "file": "string",
  "data": {
    "column_name": "value",
    ...
  }
}
```

**Output Schema:**
```json
{
  "success": true,
  "data": {
    "inserted_row": { ... },
    "new_row_count": 543
  }
}
```

**Internal Logic:**
1. Load DataFrame from DataStore
2. Validate: check all required columns exist (via `Validator.validate_insert`)
3. Type-coerce each value to match the column's existing dtype
4. Auto-assign a new ID if an ID column exists and is not provided (max existing ID + 1)
5. Build new row as dict, then as a single-row DataFrame
6. `df = pd.concat([df, new_row_df], ignore_index=True)`
7. Save back to DataStore and set dirty flag
8. Trigger `save_to_excel(file)` (auto-persist)

**Edge Cases:**
- Missing required column value → return error listing which columns are missing
- Duplicate ID → auto-increment to next available
- Extra columns not in schema → ignore with a warning note in response

---

### Tool 7: `update_row`

**Purpose:** Modify one or more fields of one or more existing rows.

**Input Schema:**
```json
{
  "file": "string",
  "filters": [ ... ],
  "updates": {
    "column_name": "new_value",
    ...
  }
}
```

**Output Schema:**
```json
{
  "success": true,
  "data": {
    "rows_updated": 3,
    "preview": [ {...} ]
  }
}
```

**Internal Logic:**
1. Load DataFrame
2. Apply filters to get the mask: `mask = build_filter_mask(df, filters)`
3. Validate: `df[mask].shape[0] > 0` — if zero rows match, return error
4. For each key in `updates`:
   - Validate column exists
   - Type-coerce new value
   - `df.loc[mask, col] = new_value`
5. Save to DataStore, set dirty flag, persist to Excel
6. Return count of updated rows + preview of updated rows

**Edge Cases:**
- No filters provided → this would update ALL rows; require confirmation signal or return an error asking user to confirm with explicit `confirm: true` flag
- Update column doesn't exist → return error
- Filters match 0 rows → return informative "no rows matched" error

---

### Tool 8: `delete_row`

**Purpose:** Delete one or more rows matching filters.

**Input Schema:**
```json
{
  "file": "string",
  "filters": [ ... ],
  "confirm": "bool  // must be true to proceed"
}
```

**Output Schema:**
```json
{
  "success": true,
  "data": {
    "rows_deleted": 2,
    "new_row_count": 540
  }
}
```

**Internal Logic:**
1. Load DataFrame
2. Apply filters to get mask
3. Count matching rows: `n = df[mask].shape[0]`
4. If `confirm == false` or not provided:
   - Return a "preview" response: "This will delete N rows. Please confirm."
   - Set a pending-action in session state (see Agent Memory)
5. If `confirm == true`:
   - `df = df[~mask].reset_index(drop=True)`
   - Save to DataStore, persist to Excel
   - Return rows_deleted count

**Edge Cases:**
- No filters → block deletion of entire table; require explicit `delete_all: true` flag as additional safeguard
- Zero rows match filters → return informative error
- Confirm not provided on destructive action → always prompt for confirmation

---

### Tool 9: `get_row_by_id`

**Purpose:** Fetch a single row by its primary key / ID column. Fast path for "show me listing 42".

**Input Schema:**
```json
{
  "file": "string",
  "id_column": "string",
  "id_value": "any"
}
```

**Output Schema:**
```json
{
  "success": true,
  "data": {
    "row": { ... }
  }
}
```

**Internal Logic:**
1. Load DataFrame
2. `result = df[df[id_column] == id_value]`
3. If empty → return not found error
4. Return first match as dict (IDs should be unique; if multiple match, return all with a warning)

---

### Tool Registry Map

```python
TOOL_REGISTRY = {
    "describe_schema":   tools.schema.describe_schema,
    "read_data":         tools.read.read_data,
    "query_data":        tools.query.query_data,
    "aggregate_data":    tools.aggregate.aggregate_data,
    "sort_data":         tools.sort.sort_data,
    "insert_row":        tools.insert.insert_row,
    "update_row":        tools.update.update_row,
    "delete_row":        tools.delete.delete_row,
    "get_row_by_id":     tools.get_by_id.get_row_by_id,
}
```

---

## 5. DATA HANDLING DESIGN

### Loading Strategy

At startup, `DataStore.initialize()` is called once. It:
1. Reads both Excel files from `/data/` using `pd.read_excel(path, engine='openpyxl')`
2. Stores each as a DataFrame in a dict: `{"real_estate": df1, "marketing": df2}`
3. Caches the schema (column names + dtypes) separately for quick prompt injection

### File Name Aliases

The LLM is told to use short keys: `real_estate` and `marketing`. A mapping resolves these:

```python
FILE_MAP = {
    "real_estate": "data/real_estate_listings.xlsx",
    "marketing":   "data/marketing_campaigns.xlsx"
}
```

The LLM never needs to know the full file path.

### In-Memory Data Structure

```python
class DataStore:
    _data: dict[str, pd.DataFrame]  # keyed by alias
    _dirty: dict[str, bool]          # dirty flag per file
    _schema_cache: dict[str, list]   # cached schema per file
```

### Persistence Strategy

- **Reads**: Never write to disk
- **Mutations** (insert/update/delete): Immediately write back to disk after every operation using `df.to_excel(path, index=False, engine='openpyxl')`
- This ensures the user never loses data if the session crashes
- The dirty flag is cleared after each successful save

### Schema Difference Handling

The two files have entirely different columns. The schema is always file-specific. The LLM always knows which file it is querying (it determines this from context), so column-level operations are always scoped to one file. Cross-file joins are not supported (out of scope for this task).

### Data Type Inference & Coercion

At load time, pandas auto-infers dtypes. We additionally apply:
- Date columns: try `pd.to_datetime()` on string columns that look like dates
- Numeric columns: ensure they're float64 or int64, not object
- String columns: kept as object

When inserting/updating, values are coerced to the column's stored dtype before writing. If coercion fails, the tool returns a type error.

### Validation Strategy

`Validator` class (in `utils/validator.py`):

- `validate_insert(file, data_dict)`: checks all non-nullable columns are present and values are the right type
- `validate_update(file, column, value)`: checks column exists and value is coercible
- `validate_filters(file, filters)`: checks each filter's column exists and operator is valid

---

## 6. FUNCTION-LEVEL DESIGN

### `main.py` — `run_session()`

```
Parameters: None
Returns: None

Logic:
1. Call DataStore.initialize()
2. Call describe_schema for both files (build schema context string)
3. Initialize conversation_history = []
4. Print welcome message
5. Loop:
   a. user_input = input("You: ").strip()
   b. If user_input in ["exit","quit"] → break
   c. If user_input == "" → continue
   d. response = agent.process(user_input, conversation_history)
   e. conversation_history.append({"role":"user","content":user_input})
   f. conversation_history.append({"role":"assistant","content":response})
   g. print("Assistant:", response)
6. Print goodbye message
```

---

### `agent/agent.py` — `process(user_input, history)`

```
Parameters:
  user_input: str
  history: list[dict]
Returns: str (the final answer to show the user)

Logic:
1. Build system_prompt using PromptBuilder.build_system_prompt(schema_context, tool_catalog)
2. Build messages = history[-6:] + [{"role":"user","content":user_input}]
3. Call llm_client.complete(system_prompt, messages) → raw_response: str
4. Parse raw_response as JSON → parsed
5. Validate parsed structure (has "type", "tool"/"steps" fields)
   If validation fails:
     a. Build correction_prompt with the error
     b. Retry llm_client.complete() once
     c. If still fails: return "I'm sorry, I couldn't understand that request."
6. If parsed.type == "single":
   a. result = tool_registry.execute(parsed.tool, parsed.arguments)
   b. If result.success:
      - return formatter.format_result(parsed.tool, result.data)
   c. Else:
      - return formatter.format_error(result.error)
7. If parsed.type == "multi":
   a. accumulated_results = []
   b. For each step in parsed.steps:
      - If step.uses_previous: inject last result into step.arguments
      - result = tool_registry.execute(step.tool, step.arguments)
      - accumulated_results.append(result)
      - If not result.success: break early, return error
   c. return formatter.format_multi_result(accumulated_results)
8. If parsed.type == "answer" (LLM has enough context to answer directly):
   a. return parsed.answer
```

---

### `agent/prompt_builder.py` — `build_system_prompt(schema_context, tool_catalog)`

```
Parameters:
  schema_context: str (pre-built string of column names/types per file)
  tool_catalog: str (pre-built string of all tools with arg schemas)
Returns: str

Logic:
1. Load base prompt template from prompts/system_prompt.txt
2. Replace {SCHEMA_CONTEXT} placeholder with schema_context
3. Replace {TOOL_CATALOG} placeholder with tool_catalog
4. Return assembled string

This function is called once per session startup.
The schema_context is built by describe_schema at startup.
The tool_catalog is a static string defined in prompts/tool_catalog.txt.
```

---

### `agent/tool_registry.py` — `execute(tool_name, arguments)`

```
Parameters:
  tool_name: str
  arguments: dict
Returns: ToolResult(success: bool, data: dict|None, error: str|None)

Logic:
1. fn = TOOL_REGISTRY.get(tool_name)
2. If fn is None:
   return ToolResult(success=False, error=f"Unknown tool: {tool_name}")
3. Try:
   result = fn(**arguments)
   return result
4. Except TypeError as e:  (wrong arguments)
   return ToolResult(success=False, error=f"Invalid arguments: {str(e)}")
5. Except Exception as e:
   log_error(tool_name, arguments, e)
   return ToolResult(success=False, error=f"Tool execution failed: {str(e)}")
```

---

### `utils/excel_io.py` — `load_excel(file_alias)` and `save_excel(file_alias, df)`

```
load_excel(file_alias: str) → pd.DataFrame:
1. path = FILE_MAP[file_alias]
2. Verify path exists; raise FileNotFoundError if not
3. df = pd.read_excel(path, engine='openpyxl')
4. Strip whitespace from all string columns
5. Attempt date parsing on columns with 'date'/'time' in their name
6. Return df

save_excel(file_alias: str, df: pd.DataFrame) → None:
1. path = FILE_MAP[file_alias]
2. df.to_excel(path, index=False, engine='openpyxl')
3. Log: "Saved {file_alias} to {path} ({len(df)} rows)"
```

---

### `utils/validator.py` — `validate_insert(file_alias, data_dict)`

```
Parameters:
  file_alias: str
  data_dict: dict
Returns: ValidationResult(valid: bool, errors: list[str])

Logic:
1. df = DataStore.get(file_alias)
2. known_cols = set(df.columns)
3. errors = []
4. For each col in known_cols:
   a. If col has no nulls in existing data (proxy for "required"):
      if col not in data_dict and col is not an ID column:
        errors.append(f"Missing required column: {col}")
5. For each key, value in data_dict.items():
   a. If key not in known_cols: add warning (not error — we skip unknown cols)
   b. Try to coerce value to dtype of df[key]
   c. If coercion fails: errors.append(f"Type error for {key}: expected {dtype}")
6. Return ValidationResult(valid=len(errors)==0, errors=errors)
```

---

### `utils/formatter.py` — `format_result(tool_name, data)`

```
Parameters:
  tool_name: str
  data: dict
Returns: str (human-readable text)

Logic:
1. Dispatch by tool_name:
   - "query_data" / "read_data": 
       If data.rows is empty: return "No results found matching your criteria."
       Else: build a table-like string using tabulate or manual formatting
             Include summary line: "Found {matched_rows} of {total_rows} records."
   - "aggregate_data":
       If scalar: "The {operation} of {column} is {result}"
       If grouped: tabulate group results
   - "insert_row": "Successfully added new row. Total rows: {new_row_count}"
   - "update_row": "Updated {rows_updated} row(s) successfully."
   - "delete_row": "Deleted {rows_deleted} row(s). Remaining: {new_row_count}"
   - "describe_schema": tabulate column info
   - default: str(data)
2. Return formatted string
```

---

### `utils/llm_client.py` — `complete(system_prompt, messages)`

```
Parameters:
  system_prompt: str
  messages: list[dict]
Returns: str (raw LLM response)

Logic:
1. Build request payload per Groq/Gemini API spec
2. Add system message: {"role": "system", "content": system_prompt}
3. Combine with messages
4. POST to API endpoint with API key from env var
5. Extract text content from response
6. Return raw string
7. On HTTP error: raise LLMError with status code and body
8. On timeout: raise LLMError("LLM request timed out")
```

---

### `tools/query.py` — `query_data(file, filters, columns, limit)`

```
Parameters:
  file: str
  filters: list[dict]
  columns: list[str] | None
  limit: int | None  (default 50)
Returns: ToolResult

Logic:
1. df = DataStore.get(file)  → copy to avoid mutation
2. For each filter dict f in filters:
   a. col = resolve_column(df, f["column"])   # case-insensitive lookup
   b. op  = f["operator"]
   c. val = f["value"]
   d. Apply operator mask (see section 4, Tool 3)
   e. df = df[mask]
3. If columns:
   a. valid_cols = [c for c in columns if c in df.columns]
   b. df = df[valid_cols]
4. matched = len(df)
5. df = df.head(limit or 50)
6. rows = df.to_dict(orient="records")
7. Return ToolResult(success=True, data={
       "rows": rows, 
       "matched_rows": matched, 
       "total_rows": len(DataStore.get(file))
   })
```

---

## 7. END-TO-END FLOW EXAMPLES

### Example A: Simple Query

**User:** `"Show me the top 5 most expensive listings in California"`

**Agent Reasoning (inside LLM):**
- File: `real_estate`
- Need to filter by state = CA
- Need to sort by price descending
- Limit 5
- Single step: use `query_data` with filters + sort embedded, OR chain `query_data` then `sort_data`

**LLM Output JSON:**
```json
{
  "type": "multi",
  "plan": ["Filter CA listings", "Sort by price desc", "Limit 5"],
  "steps": [
    {
      "tool": "query_data",
      "arguments": {
        "file": "real_estate",
        "filters": [{"column": "state", "operator": "eq", "value": "CA"}],
        "limit": 500
      }
    },
    {
      "tool": "sort_data",
      "arguments": {
        "file": "real_estate",
        "filters": [{"column": "state", "operator": "eq", "value": "CA"}],
        "sort_by": [{"column": "price", "ascending": false}],
        "limit": 5
      }
    }
  ]
}
```

*(In practice the agent collapses this to a single sort_data call with filters)*

**Tool Execution:** `sort_data` returns 5 rows sorted by price desc

**Formatter Output:**
```
Here are the 5 most expensive listings in California:

 # │ Address              │ City          │ Price        │ Beds │ Baths
───┼──────────────────────┼───────────────┼──────────────┼──────┼──────
 1 │ 12 Sunset Blvd       │ Beverly Hills │ $4,200,000   │  6   │  5
 2 │ ...
```

---

### Example B: Complex Multi-Step Query

**User:** `"Which state has the highest average listing price, and how many listings does it have?"`

**LLM Output JSON:**
```json
{
  "type": "multi",
  "steps": [
    {
      "tool": "aggregate_data",
      "arguments": {
        "file": "real_estate",
        "column": "price",
        "operation": "mean",
        "group_by": "state"
      }
    },
    {
      "tool": "aggregate_data",
      "arguments": {
        "file": "real_estate",
        "column": "id",
        "operation": "count",
        "group_by": "state"
      }
    }
  ]
}
```

**Agent:** Merges both results in the formatter, identifies the state with max mean price.

**Final Answer:**
```
Hawaii (HI) has the highest average listing price at $1,240,000.
It has 34 listings in the dataset.
```

---

### Example C: Insert Operation

**User:** `"Add a new listing: 3-bed 2-bath condo in Austin TX, price $385,000, listed today"`

**LLM Output JSON:**
```json
{
  "type": "single",
  "tool": "insert_row",
  "arguments": {
    "file": "real_estate",
    "data": {
      "bedrooms": 3,
      "bathrooms": 2,
      "property_type": "condo",
      "city": "Austin",
      "state": "TX",
      "price": 385000,
      "listing_date": "2026-04-24"
    }
  }
}
```

**Validator:** Checks for required columns, auto-assigns ID = max(id) + 1

**Response:** `"New listing added successfully with ID 543. Total listings: 543."`

---

### Example D: Delete with Confirmation

**User:** `"Delete all marketing campaigns with ROI below 10%"`

**First LLM call response:**
```json
{
  "type": "single",
  "tool": "delete_row",
  "arguments": {
    "file": "marketing",
    "filters": [{"column": "roi", "operator": "lt", "value": 10}],
    "confirm": false
  }
}
```

**Agent Response to user:** `"This will delete 8 campaigns with ROI below 10%. Type 'yes, confirm deletion' to proceed."`

**User:** `"yes, confirm deletion"`

**Second LLM call:** Recognizes this as a confirmation for a pending delete action. Sets `confirm: true`.

**Response:** `"Deleted 8 campaigns. Remaining: 47 campaigns."`

---

### Example E: Ambiguous Query

**User:** `"What's the average?"`

**LLM recognizes:** Ambiguous — no file, no column specified.

**LLM Output JSON:**
```json
{
  "type": "clarify",
  "question": "Could you clarify? Average of which column — and for which file? For example: 'average price of real estate listings' or 'average clicks in marketing campaigns'."
}
```

**Agent:** Returns the clarification question directly to the user without calling any tool.

---

## 8. LLM INTEGRATION

### Recommended Free LLM Options (Ranked)

| Option | Model | Context | Speed | Notes |
|---|---|---|---|---|
| **Groq** (primary) | `llama-3.3-70b-versatile` | 128k | Very fast | Best free JSON output reliability |
| **Gemini Free Tier** | `gemini-1.5-flash` | 1M | Fast | Generous free quota |
| **OpenRouter** | `mistral-7b-instruct` | 32k | Medium | Many free model options |
| **NVIDIA Build** | `llama-3.1-70b` | 128k | Fast | Good for structured output |

**Primary choice: Groq with Llama 3.3 70B.** Groq's latency (~200ms) is exceptional for a conversational loop, and Llama 3.3 70B reliably follows JSON output instructions.

**Fallback: Gemini 1.5 Flash.** If Groq rate limits hit (the free tier is generous but finite), switch via env var `LLM_PROVIDER=gemini`.

### Prompt Design Strategy

The prompt is divided into three layers:

**Layer 1 — System Prompt (static per session):**
```
You are a data assistant that helps users query and modify Excel files.

## Available Files and Their Schemas

### real_estate (real_estate_listings.xlsx)
Columns: id (int), address (str), city (str), state (str), price (float),
         bedrooms (int), bathrooms (float), sqft (float), listing_date (date),
         property_type (str), status (str)
Row count: 542

### marketing (marketing_campaigns.xlsx)
Columns: id (int), campaign_name (str), channel (str), budget (float),
         spend (float), impressions (int), clicks (int), conversions (int),
         roi (float), start_date (date), end_date (date), status (str)
Row count: 55

## Available Tools
[...tool catalog with full argument schemas...]

## Response Format
You MUST respond ONLY with valid JSON. No preamble, no prose. Use one of:
{"type":"single","tool":"<name>","arguments":{...}}
{"type":"multi","steps":[{"tool":"<name>","arguments":{...}},...],"plan":[...]}
{"type":"clarify","question":"..."}
{"type":"answer","answer":"..."}
```

**Layer 2 — Conversation History (rolling 6 turns):**
The last 3 user+assistant exchanges provide conversational context.

**Layer 3 — Current User Message:**
The raw user input, unchanged.

### JSON Output Enforcement

- Instruct the LLM explicitly: "Respond ONLY with JSON. No markdown. No explanation."
- Use `response_format: {"type": "json_object"}` if the API supports it (Groq does)
- Fallback: strip markdown fences (```` ```json ... ``` ````) before parsing
- Double-retry mechanism: if parsing fails, send a correction message

---

## 9. ERROR HANDLING & ROBUSTNESS

### Error Categories and Handling

| Error Type | Detection Point | Response Strategy |
|---|---|---|
| **LLM parse failure** | Agent, after LLM call | Retry once with correction prompt; if still fails, return friendly error |
| **Unknown tool name** | Tool Registry | Return error: "I tried to use an unknown tool. Please rephrase." |
| **Invalid arguments** | Tool executor (TypeError) | Return error with what was expected |
| **Column not found** | Each tool | Return error listing available columns |
| **Type mismatch** | Validator | Return specific type error with column name |
| **File not found** | excel_io.load | Fatal at startup; exit with clear message |
| **No rows matched** | query/update/delete tools | Informative "no results" — not an error |
| **Destructive without confirm** | delete/update tools | Ask for confirmation, store pending action |
| **LLM rate limit (429)** | LLM client | Retry after 5s sleep, up to 3 times; then fail with message |
| **LLM timeout** | LLM client | Return "The AI is slow to respond. Please try again." |
| **Ambiguous query** | LLM (type=clarify) | Return clarification question to user |

### Pending Action System

For destructive operations (delete, bulk update), the agent stores a pending action in session state:

```python
session_state = {
    "pending_action": {
        "tool": "delete_row",
        "arguments": {...},
        "expires_at": time.time() + 60  # expires in 60 seconds
    }
}
```

When the user's next message is detected as a confirmation ("yes", "confirm", "proceed"), the agent checks for a pending action and executes it. If the pending action has expired, it tells the user to re-issue the command.

### Logging

Every step is logged to `logs/session_{timestamp}.log`:
- User input
- LLM raw output
- Tool called + arguments
- Tool result (success/failure)
- Final response

This is invaluable for debugging and defending design choices in the live call.

---

## 10. PROJECT STRUCTURE

```
ai_excel_assistant/
│
├── main.py                      # Entry point; REPL loop
│
├── agent/
│   ├── __init__.py
│   ├── agent.py                 # Core agent orchestration loop
│   ├── prompt_builder.py        # Assembles LLM system prompt
│   └── tool_registry.py         # Maps tool names to functions; dispatcher
│
├── tools/
│   ├── __init__.py
│   ├── schema.py                # describe_schema tool
│   ├── read.py                  # read_data tool
│   ├── query.py                 # query_data tool
│   ├── aggregate.py             # aggregate_data tool
│   ├── sort.py                  # sort_data tool
│   ├── insert.py                # insert_row tool
│   ├── update.py                # update_row tool
│   ├── delete.py                # delete_row tool
│   └── get_by_id.py             # get_row_by_id tool
│
├── data/
│   ├── store.py                 # DataStore singleton (in-memory DataFrames)
│   ├── real_estate_listings.xlsx
│   └── marketing_campaigns.xlsx
│
├── utils/
│   ├── __init__.py
│   ├── excel_io.py              # load_excel / save_excel
│   ├── validator.py             # Insert/update/filter validation
│   ├── formatter.py             # Converts tool results to readable strings
│   ├── llm_client.py            # HTTP calls to Groq/Gemini API
│   ├── logger.py                # Structured session logging
│   └── types.py                 # ToolResult, ValidationResult dataclasses
│
├── prompts/
│   ├── system_prompt.txt        # Base system prompt template
│   └── tool_catalog.txt         # Static JSON tool description block
│
├── logs/                        # Auto-created; session log files
│
├── tests/
│   ├── test_tools.py            # Unit tests for each tool
│   ├── test_agent.py            # Integration tests for agent flow
│   ├── test_validator.py        # Validator unit tests
│   └── fixtures/                # Small test Excel files
│
├── .env.example                 # GROQ_API_KEY=, LLM_PROVIDER=groq
├── requirements.txt             # pandas, openpyxl, requests, tabulate, python-dotenv
├── README.md
└── DECISIONS.md
```

### File Responsibilities Summary

| File | Role |
|---|---|
| `main.py` | Session entry point, REPL, startup initialization |
| `agent/agent.py` | The brain — orchestrates LLM → tool → response pipeline |
| `agent/prompt_builder.py` | Builds the structured prompt injected into every LLM call |
| `agent/tool_registry.py` | Single source of truth for what tools exist and how to call them |
| `tools/*.py` | Pure data operation functions; no LLM calls ever |
| `data/store.py` | In-memory singleton; single source of truth for DataFrames |
| `utils/excel_io.py` | All disk I/O; isolated so it can be swapped for a DB later |
| `utils/validator.py` | Guards all write operations against bad data |
| `utils/formatter.py` | All presentation logic; keeps tools clean |
| `utils/llm_client.py` | All HTTP networking; isolated for easy provider swap |
| `utils/types.py` | Shared dataclasses so every file speaks the same type language |
| `prompts/` | Externalized prompt text; change prompts without touching code |

---

## 11. DESIGN DECISIONS & TRADEOFFS

### Decision 1: Single LLM call per turn (not a ReAct loop)

**Choice:** One structured LLM call that can output either a single tool call or a planned sequence of steps.

**Alternative:** A ReAct loop where the LLM calls one tool, sees the result, then decides the next tool (like LangChain's AgentExecutor).

**Tradeoff:** ReAct is more flexible for truly open-ended tasks, but adds latency (N LLM calls per turn). For this scoped task (two known files, known schema), a single planning call is sufficient and 3–5x faster. The schema is small enough to fit in one prompt.

---

### Decision 2: In-memory DataStore, write-through on mutation

**Choice:** Load everything into memory at startup, write back to disk on every mutation.

**Alternative:** Read from disk on every tool call.

**Tradeoff:** Memory usage vs. I/O latency. For Excel files likely under 100MB, in-memory is fine and makes reads instantaneous. The write-through pattern ensures durability without needing a transaction system.

---

### Decision 3: JSON-based tool calling over code generation

**Choice:** The LLM outputs structured JSON that the agent interprets, not executable Python code.

**Alternative:** Let the LLM generate Python/pandas code and `exec()` it.

**Tradeoff:** Code generation is more flexible (can handle any query in theory) but is a significant security risk (`exec()` is dangerous), harder to validate, and harder to debug. JSON tool calling is safer, predictable, and testable.

---

### Decision 4: Groq + Llama 3.3 70B as primary LLM

**Choice:** Groq for speed; Llama 3.3 70B for JSON instruction-following quality.

**Alternative:** Local Ollama model (fully free, no rate limits).

**Tradeoff:** Local models require a GPU or are very slow on CPU. For a 3-day task with a live demo, Groq's free tier is more than sufficient and dramatically more reliable.

---

### Decision 5: No vector search / RAG

**Choice:** Pass the full schema in every prompt, no embedding or retrieval.

**Alternative:** Use embeddings to retrieve only relevant columns/rows.

**Tradeoff:** RAG adds complexity without benefit here. The schemas are small (< 20 columns each). Fitting both schemas in the prompt is trivial.

---

### What I'd Do Differently With More Time

- Add a **streaming response** (SSE) for better UX on slow queries
- Add **undo support** (keep a mutation log so deletions can be reversed in-session)
- Add a **web UI** (simple Flask + HTMX frontend) instead of CLI
- Add **persistent session memory** so the user can say "same as last time"
- Add **test coverage** beyond happy paths (malformed Excel, concurrent sessions)
- Consider **SQLite as a backing store** instead of Excel for better query performance at scale

---

## 12. OPEN QUESTIONS

Before implementation begins, the following should be clarified:

1. **Do the Excel files have an ID/primary key column?** If not, we need a strategy for uniquely identifying rows for update/delete (row index vs. content-based matching).

2. **What are the actual column names in both files?** The schema tool handles discovery, but knowing them upfront allows us to write better prompt examples and validators.

3. **Are there any columns that should be treated as required when inserting?** (i.e., is it valid to insert a listing without a price?)

4. **What is the expected dataset size?** (Hundreds of rows vs. tens of thousands changes the formatter's display strategy significantly.)

5. **Should the assistant support multi-file queries?** (e.g., "How does campaign spend in Texas compare to the number of listings there?") This would require a join tool — considerably more complex.

6. **Is a CLI interface sufficient, or is a web/chat UI expected?** The task says "assistant" which could imply either.

7. **Should deleted data be truly deleted, or soft-deleted (status flag)?** Soft delete is safer and recoverable.

---

*Document authored by: Senior AI Systems Architect*
*Target audience: Implementation Engineer / AI Coding Agent*
*Status: Ready for implementation upon confirmation of Open Questions*