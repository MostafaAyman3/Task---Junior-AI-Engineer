# Implementation Tweaks (Edge Case Protections)

This document contains critical micro-adjustments that must be applied during the coding phase to prevent runtime crashes. You MUST implement these exact fixes when writing the corresponding modules.

## Tweak 1: Safe ID Generation (Empty DataFrame Protection)
**Context:** When generating a new string ID (e.g., `LST-5001` or `CMP-8001`), the logic extracts existing integer parts and finds the `max()`. 
**The Bug:** If the user deletes all rows from the Excel file, the DataFrame becomes empty. Calling `max()` on an empty pandas Series throws a `ValueError`.
**The Fix:** You must add an `if empty` check in your `insert_row` tool.

```python
# Required logic structure in tools/insert.py:
nums = df[id_col].str.replace(prefix, "").astype(int)
if nums.empty:
    # Fallback to starting numbers if table is completely empty
    new_num = 5001 if file == "real_estate" else 8001
else:
    new_num = nums.max() + 1
new_id = f"{prefix}{new_num}"
Tweak 2: Safe Date Conversion (Handling Blank Cells)
Context: When converting Excel serial dates to Python dates in utils/excel_io.py.
The Bug: There might be blank cells (NaN) or corrupted data in the date columns. Using pd.to_datetime without handling errors will crash the entire application on startup.
The Fix: You MUST use errors='coerce' inside pd.to_datetime so invalid dates gracefully become NaT (Not a Time) instead of crashing.
# Required logic structure in utils/excel_io.py during load_excel():
df["Start Date"] = pd.to_datetime(df["Start Date"] - 25569, unit='D', origin='unix', errors='coerce').dt.date
df["End Date"] = pd.to_datetime(df["End Date"] - 25569, unit='D', origin='unix', errors='coerce').dt.date