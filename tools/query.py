import pandas as pd
from data.store import DataStore
from utils.validator import resolve_column, coerce_value
from utils.constants import STATE_MAP

def build_filter_mask(df, filters):
    """
    Creates a 'filter mask' (A list of True/False values) to pick specific rows from the table.
    For example: Find all rows where City is 'New York'.
    """
    # Start by assuming all rows are included (True)
    mask = pd.Series(True, index=df.index)
    
    for f in filters:
        # Step 1: Find the real column name. "cities" -> "City"
        col = resolve_column(df, f.get("column", ""))
        if not col:
            continue
            
        op = f.get("operator", "eq") # default to 'equal' if no operator is provided
        
        # Step 2: Coerce the AI's string value into the correct Python data type (Date, Int, Float, etc.)
        val = coerce_value(df[col], f.get("value"))
        
        # Step 3: Handle special cases (Like converting "NY" to "New York")
        if col == "State" and isinstance(val, str) and len(val) == 2:
            val = STATE_MAP.get(val.upper(), val)
            
        # Step 4: Apply the mathematical filters
        if op == "eq":    # Exactly equals (City == 'New York')
            mask &= (df[col] == val)
        elif op == "gt":  # Greater than (Price > 5000)
            mask &= (df[col] > val)
        elif op == "lt":  # Less than (Price < 5000)
            mask &= (df[col] < val)
        elif op == "contains" and isinstance(val, str): # Partial text search (City contains 'York')
            mask &= df[col].astype(str).str.contains(val, case=False, na=False)
            
    # Finally, return the True/False mask which shows Exactly which rows passed all rules.
    return mask

def query_data(file_key: str, filters: list, limit: int = 10) -> dict:
    """
    Searches the database based on specific conditions provided by the AI/user.
    """
    store = DataStore()
    df = store.get_df(file_key)
    
    # Check if data exists
    if df is None or df.empty:
        return {"success": False, "error": f"The '{file_key}' datastore is empty."}
        
    # Apply our custom filter tool
    mask = build_filter_mask(df, filters)
    
    # Filter the actual table. This keeps only the rows where the Mask is True.
    result_df = df[mask]
    
    # Handle NaN formatting safely for JSON, as we did in read_data
    records = result_df.head(limit).where(pd.notnull(result_df), None).to_dict(orient="records")
    
    return {
        "success": True,
        "data": {
            "rows": records,
            "total_matched": len(result_df),
            "returned_rows": len(records)
        }
    }
