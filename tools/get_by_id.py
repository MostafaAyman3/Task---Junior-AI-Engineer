import pandas as pd
from data.store import DataStore

def get_row_by_id(file_key: str, id_val: str) -> dict:
    """
    Finds a single, specific row using its Unique ID (e.g., finding the house with Listing ID = LST-5002)
    This is much faster and more precise than using the full `query_data` tool when we know exactly 
    what we are looking for.
    """
    store = DataStore()
    df = store.get_df(file_key)
    
    if df is None or df.empty:
        return {"success": False, "error": f"The '{file_key}' datastore is empty."}
        
    id_col = "Listing ID" if file_key == "real_estate" else "Campaign ID"
    prefix = "LST-" if file_key == "real_estate" else "CMP-"
    
    # Auto-correct formatting. If AI types "5002", we force it to "LST-5002"
    id_val_str = str(id_val)
    if not id_val_str.startswith(("-", "LST-", "CMP-")) and id_val_str.isdigit():
        id_val_str = f"{prefix}{id_val_str}"
            
    # Search the table for this ID
    mask = df[id_col] == id_val_str
    result_df = df[mask]
    
    # If the search results are empty, the ID doesn't exist
    if result_df.empty:
        return {"success": False, "error": f"ID '{id_val_str}' not found in {file_key}."}
        
    # Extract the single row as a dictionary
    row = result_df.iloc[0].where(pd.notnull(result_df.iloc[0]), None).to_dict()
    return {"success": True, "data": row}
