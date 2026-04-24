import pandas as pd
from data.store import DataStore

def read_data(file_key: str, limit: int = 10) -> dict:
    """
    Reads the first few rows of a given dataset (like Real Estate or Marketing).
    
    Parameters:
    - file_key: "real_estate" or "marketing" depending on what data we want.
    - limit: The maximum number of rows to return (default is 10).
    """
    # 1. Connect to the unified DataStore (the memory manager)
    store = DataStore()
    
    # 2. Get the specific table (DataFrame) we asked for
    df = store.get_df(file_key)
    
    # 3. Safety check: What if the file wasn't loaded or is empty?
    if df is None or df.empty:
        return {"success": False, "error": f"The '{file_key}' datastore is empty/not loaded."}
        
    # 4. Format the data to send to the AI:
    # Pandas uses 'NaN' for empty cells, but standard JSON expects 'null' (Python 'None').
    # We replace NaNs with None so it converts to JSON cleanly.
    records = df.head(limit).where(pd.notnull(df), None).to_dict(orient="records")
    
    # 5. Return a successful report outlining the data shape
    return {
        "success": True,
        "data": {
            "rows": records,
            "total_rows": len(df),
            "returned_rows": len(records)
        }
    }
