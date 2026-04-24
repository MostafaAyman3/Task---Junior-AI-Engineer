from tools.read import read_data
from tools.query import query_data
from tools.insert import insert_row
from tools.update import update_row
from tools.delete import delete_row
from tools.aggregate import aggregate_data
from tools.describe import describe_schema
from tools.get_by_id import get_row_by_id

# The TOOL_REGISTRY is like a dictionary or a toolbox. 
# It maps the string names the AI uses (e.g., "read_data") directly to the actual Python functions we imported above.
# If you add a new tool in the future, you must register it here so the AI can use it.
TOOL_REGISTRY = {
    "read_data": read_data,
    "query_data": query_data,
    "insert_row": insert_row,
    "update_row": update_row,
    "delete_row": delete_row,
    "aggregate_data": aggregate_data,
    "describe_schema": describe_schema,
    "get_row_by_id": get_row_by_id
}

def execute_tool(tool_name: str, arguments: dict):
    """
    Safely executes a tool from the registry returning a standard result.
    
    What this function does:
    1. It takes the name of the tool (`tool_name`) the AI wants to use and its specific parameters (`arguments`).
    2. It looks up the actual python function in the `TOOL_REGISTRY` dictionary.
    3. If the tool is not found, it immediately stops and returns an error response.
    4. If the tool is found, it runs (executes) the function with the provided arguments using `**arguments`.
       (Explaining `**arguments`: If arguments is {"id": 1}, it runs the function like func(id=1)).
    5. It includes safety layers (try-except blocks). If the AI hallucinates and passes wrong arguments, 
       or if the tool crashes, the whole program won't shut down. Instead, it gracefully returns 
       an error dictionary back to the AI so the AI can realize its mistake and apologize or try again.
    """
    # 1. Try to find the requested tool in our dictionary
    func = TOOL_REGISTRY.get(tool_name)
    
    # 2. Check if the tool exists, if not, return an error back to the AI
    if not func:
        return {"success": False, "error": f"Tool '{tool_name}' not found."}
    
    # 3. Try to run the tool and catch any potential errors
    try:
        # **arguments unpacks the dictionary into named parameters for the function
        return func(**arguments)
    except TypeError as e:
        # Happens if the AI provided wrong parameter names that the function doesn't accept
        return {"success": False, "error": f"Invalid arguments for {tool_name}: {str(e)}"}
    except Exception as e:
        # Happens for any other general crash or bug inside the tool itself
        return {"success": False, "error": f"Execution error in {tool_name}: {str(e)}"}
