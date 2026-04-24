import json
import os
from tools.describe import describe_schema

# We define the TOOL_CATALOG structurally so the LLM knows what to call.
TOOL_CATALOG = [
    {
        "name": "read_data",
        "description": "Returns rows from a file, with optional limit. Used for generic 'show me the data'.",
        "arguments": {
            "file_key": "string ('real_estate' or 'marketing')",
            "limit": "integer (optional, default 10)"
        }
    },
    {
        "name": "query_data",
        "description": "Filters data based on conditions.",
        "arguments": {
            "file_key": "string ('real_estate' or 'marketing')",
            "filters": "array of objects: [{ 'column': 'City', 'operator': 'eq'|'gt'|'lt'|'contains', 'value': 'Boston' }]",
            "limit": "integer (optional, default 10)"
        }
    },
    {
        "name": "get_row_by_id",
        "description": "Fetch a specific row by its ID (e.g., LST-5001 or CMP-8001).",
        "arguments": {
            "file_key": "string ('real_estate' or 'marketing')",
            "id_val": "string (the ID)"
        }
    },
    {
        "name": "insert_row",
        "description": "Insert a new row. Do not provide Listing ID, Campaign ID, or computed columns (ROI, CTR, CPC, CPR).",
        "arguments": {
            "file_key": "string ('real_estate' or 'marketing')",
            "data_dict": "dictionary mapping column names to values"
        }
    },
    {
        "name": "update_row",
        "description": "Modify existing row fields.",
        "arguments": {
            "file_key": "string ('real_estate' or 'marketing')",
            "id_val": "string (the ID)",
            "data_dict": "dictionary mapping columns to updated values",
            "confirm": "boolean (false by default to preview, true to execute)"
        }
    },
    {
        "name": "delete_row",
        "description": "Remove a row by ID.",
        "arguments": {
            "file_key": "string ('real_estate' or 'marketing')",
            "id_val": "string (the ID)",
            "confirm": "boolean (false by default to preview, true to execute)"
        }
    },
    {
        "name": "aggregate_data",
        "description": "Perform group by or aggregation (mean, sum, max, min, count).",
        "arguments": {
            "file_key": "string ('real_estate' or 'marketing')",
            "agg_col": "string (the column to aggregate, e.g., 'Sale Price' or 'Budget Allocated')",
            "operation": "string ('mean'|'sum'|'max'|'min'|'count')",
            "group_by_col": "string (optional column to group by)"
        }
    }
]

def build_system_prompt() -> str:
    """Reads the template, fetches the live database schemas, and injects them."""
    prompt_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "prompts", "system_prompt.txt")
    with open(prompt_path, "r", encoding="utf-8") as f:
        template = f.read()

    # We manually build the refined schema context requested in 2_DESIGN_REFINEMENT.md
    schema_context = """
### real_estate (Real_Estate_Listings.xlsx)
Sheet: "Real Estate Listings"
Columns:
  Listing ID       (string)  — Primary key. Format: "LST-XXXX". Auto-generated on insert. Do NOT include in insert data.
  Property Type    (string)  — Values: "House", "Condo", "Apartment", "Townhouse"
  City             (string)  — Full city name (e.g., "Seattle", "Boston")
  State            (string)  — Full state name (e.g., "Texas", NOT "TX"). Translate abbreviations.
  Bedrooms         (int)
  Bathrooms        (float)   — Half-bath increments
  Square Footage   (int)
  Year Built       (int)
  List Price       (int)
  Sale Price       (float)   — NULLABLE for Active/Pending. Filter logic handles NaNs automatically. Do not require for inserts.
  Listing Status   (string)  — Values: "Sold", "Active", "Pending"

### marketing (Marketing_Campaigns.xlsx)
Sheet: "Marketing Campaigns"
Columns:
  Campaign ID      (string)  — Primary key. Format: "CMP-XXXX". Auto-generated on insert. Do NOT include in insert data.
  Campaign Name    (string)  — e.g., "Back to School - Facebook 2025 Q3"
  Channel          (string)  — Values: "Facebook", "Google Ads", "Instagram", "LinkedIn", "Email"
  Start Date       (date)    
  End Date         (date)    
  Budget Allocated (float)   
  Amount Spent     (float)   
  Impressions      (int)
  Clicks           (int)
  Conversions      (int)
  Revenue Generated(float)
  ROI (%)          (float)   — [computed] read-only.
  CTR (%)          (float)   — [computed] read-only.
  CPC              (float)   — [computed] read-only.
  CPR              (float)   — [computed] read-only.
"""

    tool_catalog_str = json.dumps(TOOL_CATALOG, indent=2)

    return template.replace("{schema_context}", schema_context).replace("{tool_catalog}", tool_catalog_str)
