import pandas as pd
import datetime

def coerce_value(col_series: pd.Series, val):
    """
    Dynamically coerce a value to match the data type of the given Pandas Series.
    Fixes TypeError: '>' not supported between instances of 'datetime.date' and 'str'
    """
    if col_series.dropna().empty:
        return val  # Cannot infer type, return as-is
        
    first_valid = col_series.dropna().iloc[0]
    
    # 1. Handle datetime.date objects
    if isinstance(first_valid, datetime.date):
        if isinstance(val, str):
            try:
                # Convert string to datetime.date
                return pd.to_datetime(val).date()
            except Exception:
                pass # Fallback if parsing fails
        return val

    # 2. Handle Numeric types
    dtype = col_series.dtype
    if pd.api.types.is_integer_dtype(dtype):
        try:
            return int(val)
        except (ValueError, TypeError):
            pass
    elif pd.api.types.is_float_dtype(dtype):
        try:
            return float(val)
        except (ValueError, TypeError):
            pass
            
    # Default: return as-is
    return val

def resolve_column(df: pd.DataFrame, user_col: str) -> str | None:
    """
    This is an 'Auto-Corrector' for column names. 
    If the AI wants "city", this function looks at the columns ("City", "Price", "State") 
    and autocorrects "city" to "City". It prevents errors due to capitalization or underscores.
    """
    cols = df.columns.tolist()
    
    # 1. Exact match (Perfect spelling)
    if user_col in cols:
        return user_col
    
    # 2. Case-insensitive (e.g. "price" -> "Price")
    user_lower = user_col.lower()
    for col in cols:
        if col.lower() == user_lower:
            return col
    
    # 3. Underscore-to-space (e.g., "budget_allocated" -> "Budget Allocated")
    normalized = user_col.replace("_", " ")
    for col in cols:
        if col.lower() == normalized.lower():
            return col
    
    # 4. Partial Text search (e.g., "budget" matches "Budget Allocated")
    for col in cols:
        if user_lower in col.lower() or col.lower() in user_lower:
            return col
            
    # If we made it this far, the column definitely does not exist.
    return None

def validate_insert(file_key: str, data_dict: dict) -> dict:
    """
    A security guard function. Before we insert or update any data, 
    we must ensure the AI isn't trying to hack or override essential locked fields.
    """
    # Rule 1: You cannot insert your own ID. IDs are generated automatically by the program!
    if file_key == "real_estate":
        data_dict.pop("Listing ID", None)
    elif file_key == "marketing":
        data_dict.pop("Campaign ID", None)
        
    # Rule 2: You cannot manually set math calculations (like ROI). 
    # They are dynamically generated when the file loads.
    COMPUTED_COLS = ["ROI (%)", "CTR (%)", "CPC", "CPR"]
    for c in COMPUTED_COLS:
        data_dict.pop(c, None)
        
    return data_dict
