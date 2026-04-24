import pandas as pd
from data.store import DataStore
from utils.validator import resolve_column, validate_insert, coerce_value

def format_id(file_key, id_val):
    """
    Helper function to fix formatting if the AI forgets the prefix. 
    If it sends "5001" instead of "LST-5001", this adds the "LST-".
    """
    prefix = "LST-" if file_key == "real_estate" else "CMP-"
    id_val_str = str(id_val)
    if not id_val_str.startswith(("-", "LST-", "CMP-")) and id_val_str.isdigit():
         return f"{prefix}{id_val_str}"
    return id_val_str

def update_row(file_key: str, id_val: str, data_dict: dict, confirm: bool = False) -> dict:
    """
    Updates specific information in an existing row without changing the other details.
    
    IMPORTANT SAFETY FEATURE: `confirm=False` by default. This means the AI must ask the user
    for permission before actually editing the database to prevent accidental data loss.
    """
    store = DataStore()
    df = store.get_df(file_key)
    
    if df is None or df.empty:
        return {"success": False, "error": "Datastore is empty."}
        
    id_col = "Listing ID" if file_key == "real_estate" else "Campaign ID"
    id_val_str = format_id(file_key, id_val)
    
    # Check if the requested ID actually exists in our table
    mask = df[id_col] == id_val_str
    if not mask.any():
        return {"success": False, "error": f"ID {id_val_str} not found."}
        
    # Clean data (ensure no primary keys or computed overrides are allowed)
    data_dict = validate_insert(file_key, data_dict)
    
    # Destructive Act Preview
    # If the user hasn't explicitly said "Yes, update it", we just show them what we are ABOUT to update.
    if not confirm:
        current_row = df[mask].iloc[0].where(pd.notnull(df[mask].iloc[0]), None).to_dict()
        return {
            "success": True,
            "preview": True,
            "message": f"Please confirm update for {id_val_str}.",
            "before": current_row,
            "updates": data_dict
        }
        
    # Apply Updates
    # We iterate through the dictionary of changes (e.g., {"Price": 300000}) and apply them to the matched row.
    for k, v in data_dict.items():
        col = resolve_column(df, k)
        if col:
            new_val = coerce_value(df[col], v)
            df.loc[mask, col] = new_val
            
    # Save the updated table back to memory and Excel
    store.set_df(file_key, df)
    
    # Grab the newly updated row to show the AI/user that it was successful
    updated_row = df[mask].iloc[0].where(pd.notnull(df[mask].iloc[0]), None).to_dict()
    
    return {"success": True, "data": {"updated_id": id_val_str, "row": updated_row}}
