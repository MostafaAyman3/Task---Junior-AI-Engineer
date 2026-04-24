import pandas as pd
from data.store import DataStore

def describe_schema(file_key: str) -> dict:
    """
    Returns the "Schema" (the structure) of the table. 
    It tells the AI exactly what columns exist, what type of data is in them 
    (number, text, date), and shows 1 example value for each.
    """
    store = DataStore()
    df = store.get_df(file_key)
    
    if df is None:
        return {"success": False, "error": "Datastore not initialized or empty."}
        
    columns_info = []
    
    # Loop through each column (e.g., 'Price', 'City', 'Status')
    for col in df.columns:
        # Get the first actual value (dropping empty/NaN cells) to show as a sample
        first_valid = df[col].dropna().iloc[0] if not df[col].dropna().empty else None
        
        # Serialize python dates gracefully to string so JSON doesn't throw an error
        if isinstance(first_valid, pd.Timestamp):
            first_valid = first_valid.isoformat()
        elif hasattr(first_valid, "isoformat"):
             first_valid = first_valid.isoformat()
             
        columns_info.append({
            "name": col,               # e.g., 'Price'
            "dtype": str(df[col].dtype), # e.g., 'int64' (a number in pandas)
            "sample": first_valid        # e.g., 250000
        })
        
    return {
        "success": True,
        "data": {
            "columns": columns_info,
            "row_count": len(df) # Tells the AI how big the dataset is
        }
    }
