import pandas as pd
import os
from utils.excel_io import load_marketing_campaigns, load_real_estate, save_excel

class DataStore:
    """
    Singleton implementation holding the in-memory pandas DataFrames.
    
    A "Singleton" means that no matter how many times you try to create a new `DataStore()` 
    anywhere in your code, Python will always return the exact same, single instance.
    This ensures all parts of the app are looking at the exact same data in memory.
    """
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        # If the instance doesn't exist yet, create it. Otherwise, return the existing one.
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.real_estate_df = None
            cls._instance.marketing_df = None
            cls._instance.real_estate_path = None
            cls._instance.marketing_path = None
        return cls._instance
        
    def initialize(self, real_estate_path: str, marketing_path: str):
        """
        Loads the Excel files from the hard drive into the computer's fast memory (RAM) 
        using Pandas DataFrames.
        """
        self.real_estate_path = real_estate_path
        self.marketing_path = marketing_path
        
        # Load Real Estate Listings file if it exists, otherwise create an empty table
        if os.path.exists(real_estate_path):
            self.real_estate_df = load_real_estate(real_estate_path)
        else:
            self.real_estate_df = pd.DataFrame()
            
        # Load Marketing Campaigns file if it exists, otherwise create an empty table
        if os.path.exists(marketing_path):
            self.marketing_df = load_marketing_campaigns(marketing_path)
        else:
            self.marketing_df = pd.DataFrame()
            
    def get_df(self, file_key: str) -> pd.DataFrame:
        """
        Retrieves the requested table (DataFrame) from the computer's memory.
        This is extremely fast because it doesn't read from the hard drive again.
        """
        if file_key == "real_estate":
            return self.real_estate_df
        elif file_key == "marketing":
            return self.marketing_df
        else:
            raise ValueError(f"Unknown file key: {file_key}")
            
    def set_df(self, file_key: str, df: pd.DataFrame):
        """
        Updates the table in memory AND immediately saves it to the Excel file on the hard drive.
        This is called a "Write-Through" cache. It ensures that if the program crashes 
        a second later, your data is already safely saved to the Excel file.
        """
        if file_key == "real_estate":
            self.real_estate_df = df
            if self.real_estate_path:
                save_excel(self.real_estate_df, self.real_estate_path)
        elif file_key == "marketing":
            self.marketing_df = df
            if self.marketing_path:
                save_excel(self.marketing_df, self.marketing_path)
        else:
            raise ValueError(f"Unknown file key: {file_key}")
