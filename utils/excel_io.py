import pandas as pd
import os

def load_marketing_campaigns(filepath: str) -> pd.DataFrame:
    """
    Opens the Marketing Excel file, cleans up Dates, and automatically calculates 
    math formulas (like ROI and Click-Through-Rate) as soon as the app starts.
    """
    df = pd.read_excel(filepath, engine='openpyxl')
    
    # Date conversion: Ensure they are Python Date objects so Pandas doesn't crash 
    # if it tries to do math on a string like "2024-01-01"
    for col in ["Start Date", "End Date"]:
        if col in df.columns:
            # openpyxl usually parses Excel dates correctly into datetime automatically.
            df[col] = pd.to_datetime(df[col], errors='coerce').dt.date

    # Computed Columns Guarding Against Division-by-Zero
    # We create New virtual columns in memory. But what if "Amount Spent" was 0?
    # Math rule: You can't divide by zero! So we use .replace(0, pd.NA) to say 
    # "If it's 0, pretend it's empty so Python doesn't crash."
    
    if "Revenue Generated" in df.columns and "Amount Spent" in df.columns:
        df["ROI (%)"] = ((df["Revenue Generated"] - df["Amount Spent"]) / df["Amount Spent"].replace(0, pd.NA) * 100).round(2)
        
    if "Clicks" in df.columns and "Impressions" in df.columns:
        df["CTR (%)"] = (df["Clicks"] / df["Impressions"].replace(0, pd.NA) * 100).round(4)
        
    if "Amount Spent" in df.columns and "Clicks" in df.columns:
        df["CPC"] = (df["Amount Spent"] / df["Clicks"].replace(0, pd.NA)).round(2)
        
    if "Amount Spent" in df.columns and "Conversions" in df.columns:
        df["CPR"] = (df["Amount Spent"] / df["Conversions"].replace(0, pd.NA)).round(2)
        
    return df

def load_real_estate(filepath: str) -> pd.DataFrame:
    """
    Opens the Real Estate bindings file.
    It doesn't need complex math formulas, so it just loads it directly.
    """
    df = pd.read_excel(filepath, engine='openpyxl')
    return df

def save_excel(df: pd.DataFrame, filepath: str):
    """
    Takes the table from Memory (RAM) and saves it permanently to the Excel file.
    """
    COMPUTED_COLS = ["ROI (%)", "CTR (%)", "CPC", "CPR"]
    
    # We DO NOT save the virtual columns (like ROI) back to Excel, 
    # because they change dynamically based on other numbers. 
    # We drop them first.
    df_to_save = df.drop(columns=[col for col in COMPUTED_COLS if col in df.columns], errors='ignore')
    
    # Excel correctly interprets Python datetime.date via openpyxl
    df_to_save.to_excel(filepath, index=False, engine='openpyxl')
