import pandas as pd
from data.store import DataStore
from utils.validator import resolve_column, validate_insert, coerce_value

def insert_row(file_key: str, data_dict: dict) -> dict:
    """
    Adds a new row (a new house listing or a new marketing campaign) to the database.
    
    Parameters:
    - file_key: "real_estate" or "marketing".
    - data_dict: A dictionary containing the new data (e.g., {"City": "Texas", "Price": 200000}).
    """
    store = DataStore()
    df = store.get_df(file_key)
    
    # We define the rules for automatically generating IDs. 
    # For Real Estate, IDs look like "LST-5001". For Marketing, "CMP-8001".
    PREFIX_MAP = {
        "real_estate": ("Listing ID", "LST-", 5001),
        "marketing":   ("Campaign ID", "CMP-", 8001)
    }
    
    if file_key not in PREFIX_MAP:
        return {"success": False, "error": "Unknown file_key. Use 'real_estate' or 'marketing'."}
        
    id_col, prefix, default_start = PREFIX_MAP[file_key]
    
    # Clean the input: Remove any columns the AI isn't allowed to edit 
    # (like trying to create its own ID or modifying calculated columns).
    data_dict = validate_insert(file_key, data_dict)
    
    # ID Generation & empty DataFrame protection
    # If the table is completely empty, we start with the default ID (e.g., LST-5001)
    if df is None or df.empty:
        new_id = f"{prefix}{default_start}"
        columns = list(data_dict.keys()) + [id_col]
        df = pd.DataFrame(columns=columns)
    else:
        # If there are already rows, we find the highest ID number, add 1, and make that the new ID.
        # For example, if the highest is LST-5020, the new one will be LST-5021.
        nums = df[id_col].astype(str).str.replace(prefix, "").astype(int)
        if nums.empty:
            new_id = f"{prefix}{default_start}"
        else:
            new_id = f"{prefix}{nums.max() + 1}"
            
    # Assign the newly generated ID to the data
    data_dict[id_col] = new_id
    
    # Fast loop: Coerce all AI-provided values (like Dates masquerading as strings) 
    # to match the types of the existing columns before insertion
    if not df.empty:
        coerced_dict = {}
        for k, v in data_dict.items():
            col = resolve_column(df, k)
            if col:
                coerced_dict[col] = coerce_value(df[col], v)
            else:
                coerced_dict[k] = v
        data_dict = coerced_dict
    
    # Convert the single row into a mini-DataFrame, then attach (concat) it to the bottom of the main table
    new_row = pd.DataFrame([data_dict])
    df = pd.concat([df, new_row], ignore_index=True)
    
    # Save the updated table back to memory (and to the Excel file automatically)
    store.set_df(file_key, df)
    
    return {"success": True, "data": {"inserted_id": new_id, "row": data_dict}}
