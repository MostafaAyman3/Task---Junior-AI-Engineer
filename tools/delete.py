import pandas as pd
from data.store import DataStore
from tools.update import format_id

def delete_row(file_key: str, id_val: str, confirm: bool = False) -> dict:
    """
    Deletes an entire row from the dataset (like completely removing a house listing).
    
    IMPORTANT SAFETY FEATURE: Just like update_row, this requires user confirmation first (`confirm=True`).
    Otherwise, the AI might accidentally delete data permanently!
    """
    store = DataStore()
    df = store.get_df(file_key)
    
    if df is None or df.empty:
        return {"success": False, "error": "Datastore is empty."}
        
    id_col = "Listing ID" if file_key == "real_estate" else "Campaign ID"
    id_val_str = format_id(file_key, id_val)
    
    # Find the row that matches this exact ID
    mask = df[id_col] == id_val_str
    if not mask.any():
        return {"success": False, "error": f"ID {id_val_str} not found."}
        
    # Destructive Act Preview
    # If the AI didn't provide confirmation, we just return the row it is trying to delete
    # so it can ask the user "Are you sure?"
    if not confirm:
        row_preview = df[mask].iloc[0].where(pd.notnull(df[mask].iloc[0]), None).to_dict()
        return {
            "success": True,
            "preview": True,
            "message": f"Please confirm deletion of {id_val_str}.",
            "target_row": row_preview
        }
        
    # The magical ~ symbol means "NOT". So df[~mask] means "Keep every row that is NOT the match".
    # Essentially, this filters out our target, effectively deleting it.
    df = df[~mask]
    
    # Save the updated (smaller) table back.
    store.set_df(file_key, df)
    
    return {"success": True, "message": f"Successfully deleted {id_val_str}"}
