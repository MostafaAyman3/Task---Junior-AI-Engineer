import pandas as pd
from data.store import DataStore
from utils.validator import resolve_column

def aggregate_data(file_key: str, agg_col: str, operation: str, group_by_col: str = None) -> dict:
    """
    Performs math and statistics on the data (like finding the Average price, or Total sales).
    
    Parameters:
    - file_key: 'real_estate' or 'marketing'
    - agg_col: The column we want to do math on (e.g., 'Price')
    - operation: What type of math? ('mean', 'sum', 'max', 'min', 'count')
    - group_by_col: Optional. If we want to break the math down by categories (e.g., Average price grouped by 'State').
    """
    store = DataStore()
    df = store.get_df(file_key)
    
    if df is None or df.empty:
        return {"success": False, "error": "Datastore is empty."}

    # Resolve column name (e.g., if AI asks for "price", we fix it to "Price")
    actual_col = resolve_column(df, agg_col)
    if not actual_col:
        return {"success": False, "error": f"Aggregation column '{agg_col}' not found."}
        
    # Group By Logic: Example: Total Sales PER State
    if group_by_col:
        actual_group = resolve_column(df, group_by_col)
        if not actual_group:
            return {"success": False, "error": f"Group by column '{group_by_col}' not found."}
            
        try:
            # df.groupby() puts all matching states in the same bucket before doing the math
            grouped = df.groupby(actual_group)[actual_col]
            if operation == "mean":
                result = grouped.mean()
            elif operation == "sum":
                result = grouped.sum()
            elif operation == "max":
                result = grouped.max()
            elif operation == "min":
                result = grouped.min()
            elif operation == "count":
                result = grouped.count()
            else:
                return {"success": False, "error": f"Unknown operation: {operation}"}
                
            return {
                "success": True,
                # We format the result and handle 'None' if some data was missing
                "data": {"aggregation": result.where(pd.notnull(result), None).to_dict(), "note": "Computed over non-null values if present"}
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
            
    # Simple Logic: Only do math on the whole column without breaking it down
    # Example: Average Price of ALL houses
    else:
        try:
            if operation == "mean":
                val = df[actual_col].mean()
            elif operation == "sum":
                val = df[actual_col].sum()
            elif operation == "max":
                val = df[actual_col].max()
            elif operation == "min":
                val = df[actual_col].min()
            elif operation == "count":
                val = df[actual_col].count()
            else:
                return {"success": False, "error": f"Unknown operation: {operation}"}
                
            return {
                "success": True,
                "data": {f"{operation}_{actual_col}": None if pd.isna(val) else val, "note": "Computed over non-null values if present"}
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
