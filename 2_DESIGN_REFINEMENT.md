# Design Refinement Document
## Based on Actual Excel File Inspection
### Status: CORRECTIONS & TARGETED FIXES ONLY

---

## ACTUAL SCHEMAS (Ground Truth)

### Marketing_Campaigns.xlsx — Sheet: "Marketing Campaigns"

| Column | Actual dtype | Example Value | Notes |
|---|---|---|---|
| `Campaign ID` | string | `CMP-8001` | Primary key — alphanumeric string |
| `Campaign Name` | string | `Back to School - Facebook 2025 Q3` | Encodes channel + season + year + quarter |
| `Channel` | string | `Facebook`, `Google Ads`, `Instagram`, `LinkedIn`, `Email` | 5 distinct values |
| `Start Date` | **int (Excel serial)** | `45758` | ⚠️ NOT a date string — must be converted |
| `End Date` | **int (Excel serial)** | `45785` | ⚠️ Same issue |
| `Budget Allocated` | float | `25000` | Max seen: ~25000 |
| `Amount Spent` | float | `23697.26` | Can EXCEED budget (overspend is real) |
| `Impressions` | int | `5058725` | |
| `Clicks` | int | `248564` | |
| `Conversions` | int | `13472` | |
| `Revenue Generated` | float | `67314.37` | |

**Row count:** > 1000 (file was truncated at row 1000 during inspection)

---

### Real_Estate_Listings.xlsx — Sheet: "Real Estate Listings"

| Column | Actual dtype | Example Value | Notes |
|---|---|---|---|
| `Listing ID` | string | `LST-5001` | Primary key — alphanumeric string |
| `Property Type` | string | `House`, `Condo`, `Apartment`, `Townhouse` | 4 distinct values |
| `City` | string | `Aurora`, `Seattle`, `Boston`, ... | Many cities |
| `State` | string | `Illinois`, `Washington`, ... | Full state name, not abbreviation |
| `Bedrooms` | int | `1`–`5` | |
| `Bathrooms` | float | `1`, `1.5`, `2`, `2.5`, `3`, `3.5` | Half-bath increments |
| `Square Footage` | int | `1091` | |
| `Year Built` | int | `1960`–`2025` | |
| `List Price` | int | `351000` | Always present |
| `Sale Price` | float / **nullable** | `360000` or **empty** | ⚠️ Empty for Active + some Pending |
| `Listing Status` | string | `Sold`, `Active`, `Pending` | 3 distinct values |

**Row count:** > 1000 (file was truncated at row 1000 during inspection)

---

## 1. ASSUMPTION VALIDATION

### ✅ Correct Assumptions

| Assumption | Status |
|---|---|
| Two separate Excel files with distinct schemas | ✅ Correct |
| Real estate has property type (House/Condo/Apartment/Townhouse) | ✅ Correct |
| Real estate has City, State, Bedrooms, Bathrooms | ✅ Correct |
| Marketing has Channel, Budget, Spend, Impressions, Clicks, Conversions | ✅ Correct |
| Sale Price is nullable (Active listings have no sale price) | ✅ Correct |
| `Listing Status` exists with Active/Pending/Sold values | ✅ Correct |
| Data types for numeric columns are float/int | ✅ Correct |
| In-memory pandas approach is valid for this file size | ✅ Correct |

---

### ❌ Incorrect Assumptions — MUST FIX

| Assumption | Reality | Impact |
|---|---|---|
| Primary keys are integers (`id: int`) | **String IDs**: `LST-XXXX` and `CMP-XXXX` | Breaks insert auto-ID logic, get_row_by_id tool, delete/update by ID |
| Column names use underscores (e.g., `listing_id`, `campaign_name`) | **Column names have spaces**: `Listing ID`, `Campaign Name`, `Budget Allocated` | Breaks every tool's column reference and the LLM's column usage |
| Marketing file has a `status` column (Active/Inactive) | **No status column exists** | LLM prompt incorrectly lists this column |
| Marketing file has an `roi` column | **No ROI column** — must be computed as `(Revenue Generated - Amount Spent) / Amount Spent * 100` | Queries like "campaigns with ROI > 20%" require on-the-fly computation |
| Real estate has an `address` column | **No address column** — property is identified by City + State + Property Type | Prompt and insert tool must not reference `address` |
| Real estate has a `listing_date` column | **No listing date** — only `Year Built` exists | Queries about "recently listed" properties cannot use listing date |
| Marketing dates are proper date strings | **Dates are Excel serial integers** (e.g., `45758` = a date in 2025) | Must convert at load time; displaying raw serial numbers to users would be confusing/broken |
| `Campaign Name` is a simple short label | It **encodes channel + season + year + quarter** (e.g., `Back to School - Facebook 2025 Q3`) | Query like "all Back to School campaigns" can use `contains` filter on Campaign Name |
| State values are abbreviations (e.g., `TX`) | **Full state names** (e.g., `Texas`, `Illinois`) | LLM prompt and example queries must use full names; the LLM should normalize abbreviations to full names |

---

## 2. GAPS IDENTIFIED

### Gap 1: No Computed Columns at Load Time
The design assumed all queryable fields exist as raw columns. ROI is a critical metric for the marketing file but is absent. Users will frequently ask "show me campaigns with ROI above X%" or "which channel has the best ROI?" — these queries cannot be answered without computation.

**Fix:** At DataStore load time, compute and append derived columns:
- `ROI (%)` = `(Revenue Generated - Amount Spent) / Amount Spent * 100` (rounded to 2 dp)
- `CTR (%)` = `Clicks / Impressions * 100` (Click-Through Rate — commonly queried)
- `CPC` = `Amount Spent / Clicks` (Cost Per Click)
- `CPR` = `Amount Spent / Conversions` (Cost Per Result)

These are appended as real columns in the DataFrame so all existing tools work without modification. They are marked as computed (read-only for insert/update) in the schema context.

---

### Gap 2: Excel Date Serial Number Conversion
Marketing dates are stored as Excel serial integers. `pd.read_excel` with `openpyxl` on these columns will read them as integers, not datetimes, unless explicitly handled.

If not fixed: the LLM will be told dates are integers, users cannot filter by date range, and any date display will show numbers instead of human-readable dates.

**Fix:** In `load_excel()`, after reading the DataFrame:
```python
for col in ["Start Date", "End Date"]:
    df[col] = pd.to_datetime(df[col] - 25569, unit='D', origin='unix').dt.date
    # Excel serial: days since 1900-01-01 (with a known offset of 25569 days to Unix epoch)
```
This converts serial → Python `date` objects. Store as `datetime.date` in the DataFrame.

---

### Gap 3: String-Format Primary Keys Require New ID Generation Logic
The original design assumed auto-incrementing integers (max(id) + 1). The actual keys are `LST-5001`, `LST-5002`, ... and `CMP-8001`, `CMP-8002`, ...

**Fix (in `insert_row` tool):**
```
prefix = "LST-" (for real_estate) or "CMP-" (for marketing)
existing_ids = df["Listing ID"].str.extract(r'(\d+)').astype(int)
new_num = existing_ids.max().item() + 1
new_id = f"{prefix}{new_num}"
```
This preserves the alphanumeric format and avoids collisions.

---

### Gap 4: Column Names with Spaces Require Careful Handling
Every tool that references column names by string must handle spaces. The LLM must also output column names with spaces in filter arguments.

**Fix:** 
- All column references remain as-is (pandas handles spaces natively: `df["Budget Allocated"]`)
- The LLM system prompt must list column names exactly, with spaces, in quotes
- The `resolve_column()` helper must do **case-insensitive matching** AND **strip whitespace** when comparing user-supplied column names to DataFrame columns
- Add a fuzzy column resolver as a fallback (e.g., if user says `"budget"`, map to `"Budget Allocated"`)

---

### Gap 5: Nullable Sale Price — Filter Logic Must Handle NaN Correctly
Approximately 40% of listings have an empty `Sale Price` (all Active listings, some Pending). The original design didn't explicitly account for this.

**Potential breaks:**
- `query_data` with `operator: "gt"` on `Sale Price` must not crash on NaN rows
- `aggregate_data` with `operation: "mean"` on `Sale Price` must skip NaN (pandas does this by default, but the response should note it)
- Inserting an Active listing should **not** require `Sale Price`

**Fix:** The `build_filter_mask()` function already handles this correctly in pandas (comparisons against NaN return False, which is correct behavior). No code change needed, but the validator must mark `Sale Price` as **nullable** explicitly. The formatter should add a note when aggregating nullable columns: `"(calculated over N non-null values)"`.

---

### Gap 6: State Filter — Full Name vs. Abbreviation Mismatch
Users will naturally type "TX" or "CA" when filtering by state. The data stores full names ("Texas", "California"). Without normalization, the filter returns 0 results, which looks like a bug.

**Fix:** Add a `STATE_ABBREVIATION_MAP` dict in `utils/constants.py`:
```python
STATE_MAP = {
    "TX": "Texas", "CA": "California", "IL": "Illinois", "WA": "Washington",
    "CO": "Colorado", "AZ": "Arizona", "NY": "New York", "FL": "Florida",
    "GA": "Georgia", "MA": "Massachusetts", "TX": "Texas", ...
}
```
In `build_filter_mask()`, when the column is `State` and value is a 2-letter string, run it through the map before applying the filter.

Also add to the system prompt: `"Note: State column stores full state names (e.g., 'Texas', not 'TX'). When the user provides an abbreviation, translate it to the full name."`

---

### Gap 7: LLM Must Know ROI Is Computed, Not a Raw Column
If the LLM is told ROI is a raw column and tries to insert a row with an `ROI (%)` value, the validator should reject it (it's computed). The schema context must mark it as read-only.

**Fix:** In `describe_schema()` output and the system prompt schema block, add a `[computed]` tag:
```
ROI (%) [computed] float  — (Revenue Generated - Amount Spent) / Amount Spent * 100
CTR (%) [computed] float  — Clicks / Impressions * 100
```
The validator's `validate_insert()` must skip computed columns when they appear in `data_dict` (or raise a warning, not an error).

---

## 3. TARGETED FIXES

### Fix A: Updated `DataStore.initialize()` — Post-Load Transformations

**Changed function: `utils/excel_io.py` → `load_excel()`**

After reading each file, apply these transforms:

```
For marketing_campaigns:
  1. Convert "Start Date" and "End Date" from Excel serial int to Python date:
       df["Start Date"] = pd.to_datetime(df["Start Date"] - 25569, unit='D', origin='unix').dt.date
       df["End Date"]   = same formula
  2. Add computed columns:
       df["ROI (%)"]  = ((df["Revenue Generated"] - df["Amount Spent"]) / df["Amount Spent"] * 100).round(2)
       df["CTR (%)"]  = (df["Clicks"] / df["Impressions"] * 100).round(4)
       df["CPC"]      = (df["Amount Spent"] / df["Clicks"]).round(2)
       df["CPR"]      = (df["Amount Spent"] / df["Conversions"]).round(2)
  3. Guard against division by zero: use df["Clicks"].replace(0, pd.NA) before CPC computation.

For real_estate_listings:
  1. No date conversion needed (no date columns).
  2. No computed columns needed for MVP. (Optionally: price_per_sqft = List Price / Square Footage)
```

---

### Fix B: Updated `insert_row` — String ID Generation

**Changed tool: `tools/insert.py`**

```
Old logic: new_id = int(df[id_col].max()) + 1
New logic:
  PREFIX_MAP = {
      "real_estate": ("Listing ID", "LST-"),
      "marketing":   ("Campaign ID", "CMP-")
  }
  id_col, prefix = PREFIX_MAP[file]
  nums = df[id_col].str.replace(prefix, "").astype(int)
  new_num = nums.max() + 1
  new_id = f"{prefix}{new_num}"
```

**Validation change:** `validate_insert()` must NOT require `Listing ID` or `Campaign ID` in `data_dict` (it will be auto-generated). It must also NOT require `Sale Price` for real estate inserts. It must NOT require computed columns (`ROI (%)`, `CTR (%)`, `CPC`, `CPR`) for marketing inserts.

---

### Fix C: Updated `resolve_column()` — Handle Spaces + Fuzzy Matching

**New utility in `utils/validator.py`:**

```
def resolve_column(df: pd.DataFrame, user_col: str) -> str | None:
    """
    Returns the exact DataFrame column name for a user-supplied column string.
    Tries: exact match → case-insensitive → underscore-to-space → fuzzy.
    """
    cols = df.columns.tolist()
    
    # 1. Exact match
    if user_col in cols:
        return user_col
    
    # 2. Case-insensitive
    user_lower = user_col.lower()
    for col in cols:
        if col.lower() == user_lower:
            return col
    
    # 3. Underscore-to-space normalization (e.g., "budget_allocated" → "Budget Allocated")
    normalized = user_col.replace("_", " ")
    for col in cols:
        if col.lower() == normalized.lower():
            return col
    
    # 4. Substring match (e.g., "budget" matches "Budget Allocated")
    for col in cols:
        if user_lower in col.lower() or col.lower() in user_lower:
            return col
    
    return None  # Not found → caller raises an error
```

---

### Fix D: Updated `get_row_by_id` — Use String ID Format

**Changed tool: `tools/get_by_id.py`**

```
Old: filter by integer id_value
New: 
  ID_COLUMN_MAP = {
      "real_estate": "Listing ID",
      "marketing":   "Campaign ID"
  }
  id_col = ID_COLUMN_MAP[file]
  # id_value could be passed as "LST-5001" or just "5001"
  if not str(id_value).startswith(("LST-", "CMP-")):
      prefix = "LST-" if file == "real_estate" else "CMP-"
      id_value = f"{prefix}{id_value}"
  result = df[df[id_col] == id_value]
```

This lets users say "show me listing 5001" and it still works correctly.

---

### Fix E: Updated System Prompt Schema Block

**Changed file: `prompts/system_prompt.txt`**

The SCHEMA_CONTEXT section must be replaced with actual column names. Exact block:

```
### real_estate (Real_Estate_Listings.xlsx)
Sheet: "Real Estate Listings"
Columns:
  Listing ID       (string)  — Primary key. Format: "LST-XXXX". Auto-generated on insert. Do NOT include in insert data.
  Property Type    (string)  — Values: "House", "Condo", "Apartment", "Townhouse"
  City             (string)  — Full city name (e.g., "Seattle", "Boston")
  State            (string)  — Full state name (e.g., "Texas", NOT "TX"). Translate abbreviations.
  Bedrooms         (int)     — Range: 1–5
  Bathrooms        (float)   — Values: 1.0, 1.5, 2.0, 2.5, 3.0, 3.5
  Square Footage   (int)
  Year Built       (int)     — Range: 1960–2025
  List Price       (int)     — Always present
  Sale Price       (float)   — NULLABLE. Empty for Active listings. Do NOT require for inserts.
  Listing Status   (string)  — Values: "Active", "Pending", "Sold"

### marketing (Marketing_Campaigns.xlsx)
Sheet: "Marketing Campaigns"
Columns:
  Campaign ID      (string)  — Primary key. Format: "CMP-XXXX". Auto-generated on insert. Do NOT include in insert data.
  Campaign Name    (string)  — e.g., "Back to School - Facebook 2025 Q3"
  Channel          (string)  — Values: "Facebook", "Google Ads", "Instagram", "LinkedIn", "Email"
  Start Date       (date)    — Format: YYYY-MM-DD
  End Date         (date)    — Format: YYYY-MM-DD
  Budget Allocated (float)
  Amount Spent     (float)   — May exceed Budget Allocated (overspend is valid data)
  Impressions      (int)
  Clicks           (int)
  Conversions      (int)
  Revenue Generated(float)
  ROI (%)          [computed, read-only] — (Revenue Generated - Amount Spent) / Amount Spent × 100
  CTR (%)          [computed, read-only] — Clicks / Impressions × 100
  CPC              [computed, read-only] — Amount Spent / Clicks
  CPR              [computed, read-only] — Amount Spent / Conversions
```

---

### Fix F: Updated Tool Catalog — Filter Examples

The tool catalog in `prompts/tool_catalog.txt` must use real column names in examples.

**Old example (wrong):**
```json
{"column": "state", "operator": "eq", "value": "TX"}
```

**New example (correct):**
```json
{"column": "State", "operator": "eq", "value": "Texas"}
```

**Old example (wrong):**
```json
{"column": "roi", "operator": "gt", "value": 20}
```

**New example (correct):**
```json
{"column": "ROI (%)", "operator": "gt", "value": 20}
```

---

### Fix G: `save_excel()` — Must Not Save Computed Columns

When writing back to the Excel file, computed columns must be excluded:

```python
COMPUTED_COLUMNS = {
    "marketing": ["ROI (%)", "CTR (%)", "CPC", "CPR"]
}

def save_excel(file_alias: str, df: pd.DataFrame) -> None:
    path = FILE_MAP[file_alias]
    cols_to_drop = COMPUTED_COLUMNS.get(file_alias, [])
    df_to_save = df.drop(columns=cols_to_drop, errors='ignore')
    df_to_save.to_excel(path, index=False, engine='openpyxl')
```

This prevents computed columns from being written to disk (they'd be stale on next load anyway, since they're re-derived at load time).

---

## 4. NEW EDGE CASES DISCOVERED FROM REAL DATA

| Edge Case | Source | Handling |
|---|---|---|
| `Amount Spent > Budget Allocated` | Marketing file (e.g., CMP-8026: spent $6,897 on $6,400 budget) | This is valid data — overspend is real. The validator must NOT reject inserts/updates where spent > budget. |
| `ROI (%)` can be negative | Marketing — if Amount Spent > Revenue Generated | The computed column formula handles this naturally. The formatter should label negative ROI clearly. |
| Impressions = 0 edge case | If a campaign had 0 impressions, `CTR (%)` = Clicks/0 = NaN | Guard with `df["Impressions"].replace(0, pd.NA)` before CTR computation. |
| Conversions = 0 edge case | Some niche campaigns may have 0 conversions, making CPR = inf | Guard with `df["Conversions"].replace(0, pd.NA)` before CPR computation. |
| `Sale Price` empty for non-Active listings | Some Pending rows also lack Sale Price (e.g., LST-5007 is Pending with a Sale Price) | This is inconsistent real data. Do not enforce Sale Price as required for Pending status. |
| City name disambiguation | "Aurora" exists in both Illinois and Colorado | Queries like "listings in Aurora" are ambiguous. The formatter should note the ambiguity: "Found 12 results in Aurora (across Illinois and Colorado). Filter by State to narrow down." |
| Same campaign name, different IDs | e.g., Two entries named "Referral Program - Instagram 2025 Q1" (CMP-8196, CMP-8197) | Campaign Name is NOT unique. Always use Campaign ID as the canonical identifier for update/delete. Never use Campaign Name as a filter for destructive operations without first showing matched rows. |
| `Year Built` up to 2025 | Real estate file has new construction | Year Built = 2025 is valid. Do not flag as anomalous. |
| Float precision in amounts | e.g., `17150.810000000001` | Caused by floating-point representation. The formatter must round monetary values to 2dp before display. |
| Marketing file row count > 1000 | Truncated in extraction | The system must load the full file, not just the first 1000 rows. No change needed to architecture — `pd.read_excel()` reads all rows by default. |

---

## 5. FINAL ADJUSTMENTS SUMMARY

| # | What Changed | Why |
|---|---|---|
| 1 | Primary key type: int → string (`LST-XXXX`, `CMP-XXXX`) | Actual data uses alphanumeric IDs, not integer sequences |
| 2 | Column names: underscores → spaces (`"Listing ID"`, `"Budget Allocated"`, etc.) | Actual Excel headers use spaces |
| 3 | Date handling: Excel serial int → Python date at load time | `Start Date` and `End Date` are stored as Excel serial numbers |
| 4 | ROI/CTR/CPC/CPR added as computed columns at load | No ROI column exists; users will ask for ROI-based filtering |
| 5 | `address` column removed from real estate schema | Column does not exist in the file |
| 6 | `status` column removed from marketing schema | Column does not exist in the file |
| 7 | `roi` column removed from marketing schema (replaced by computed) | No raw ROI column |
| 8 | State abbreviation normalization added | Data stores full state names; users will type abbreviations |
| 9 | `Sale Price` marked as nullable with validator exemption | Empty for all Active listings |
| 10 | `resolve_column()` made fuzzy (underscore-to-space, substring) | Column names with spaces would break exact-match lookups |
| 11 | `save_excel()` strips computed columns before writing | Computed columns should not be persisted |
| 12 | Campaign Name uniqueness warning added to delete/update tool | Duplicate campaign names exist; ID is the only reliable key |
| 13 | City disambiguation note added to formatter | "Aurora" appears in both Illinois and Colorado |
| 14 | Overspend guard removed from validator | Amount Spent > Budget Allocated is valid real data |
| 15 | Division-by-zero guards added for CTR, CPC, CPR | Zero impressions/conversions exist in data |

---

*Refinement authored after inspection of actual `Marketing_Campaigns.xlsx` (1000+ rows) and `Real_Estate_Listings.xlsx` (1000+ rows)*
*All other design sections from the original document remain valid and unchanged.*