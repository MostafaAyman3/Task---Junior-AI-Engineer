import json
import re
import logging
from typing import List, Dict

from agent.prompt_builder import build_system_prompt
from utils.llm_client import query_llm_with_fallback
from agent.tool_registry import execute_tool

logger = logging.getLogger(__name__)

class Agent:
    """
    The Agent is the ' Brain ' of the assistant. It manages the conversation history, 
    talks to the LLM (Large Language Model), and decides which tools to execute based on the LLM's requests.
    """
    def __init__(self):
        # We load the strict rules and instructions from our text file (the 'System Prompt').
        self.system_prompt = build_system_prompt()
        
        # This list saves everything the user and the bot say to each other.
        self.conversation_history: List[Dict[str, str]] = []
        
    def _clean_json_response(self, text: str) -> str:
        """
        Helper function: Sometimes the AI wraps its JSON response inside markdown blocks like:
        ```json
        { "type": "answer" }
        ```
        This code safely strips away the ```json parts so Python's json.loads() doesn't crash.
        """
        text = text.strip()
        # Use simple regular expressions (Regex) to find matching markdown fences and extract what's inside
        match = re.search(r'```(?:json)?\s*(\{.*\}|\[.*\])\s*```', text, re.DOTALL)
        if match:
            return match.group(1).strip()
        
        # Fallback: Just grab everything between the very first '{' and the very last '}'
        start = text.find('{')
        end = text.rfind('}')
        if start != -1 and end != -1:
            return text[start:end+1]
            
        return text

    def _call_llm_with_retry(self, messages: List[Dict[str, str]], retries: int = 1) -> dict:
        """
        Sends the messages to the LLM, attempts to parse the response into Python JSON format (dictionary).
        If the AI outputs broken JSON (missing commas, quotes, etc.), this function intercepts the error, 
        sends a message back to the AI telling it "You made a syntax error", and forces it to try again.
        """
        for attempt in range(retries + 1):
            raw_response = query_llm_with_fallback(messages)
            cleaned_json = self._clean_json_response(raw_response)
            
            try:
                # Try to convert the string answer into a Python dictionary
                parsed = json.loads(cleaned_json)
                
                # Check if the AI followed our rules by including a "type"
                if "type" not in parsed:
                    raise ValueError("Missing 'type' field in JSON response.")
                    
                return parsed
                
            except (json.JSONDecodeError, ValueError) as e:
                # JSON was broken! Let's tell the AI to fix it in the next attempt.
                logger.warning(f"Failed to parse LLM JSON on attempt {attempt + 1}: {e}")
                if attempt < retries:
                    error_msg = {"role": "user", "content": f"Your previous output was invalid JSON: {str(e)}. Please output ONLY valid JSON without markdown wrapping."}
                    messages.append(error_msg)
                else:
                    return {"type": "answer", "content": "I encountered an internal error parsing the system response. Please try your request again."}

    def process_message(self, user_text: str) -> str:
        """
        This is the main function called whenever the user types something in the terminal.
        """
        # Add the newest user message to our history.
        self.conversation_history.append({"role": "user", "content": user_text})
        
        # Keep history bounded - we only keep the last 12 interactions to prevent breaking the API limits (Payload Too Large Error).
        if len(self.conversation_history) > 12:
            self.conversation_history = self.conversation_history[-12:]

        # Combine the secret system instructions + the recent chat history into the payload 
        messages = [{"role": "system", "content": self.system_prompt}] + self.conversation_history
        
        # Call the helper method to get the AI's response safely.
        response_data = self._call_llm_with_retry(messages)
        
        # Determine what action the AI wants to do
        resp_type = response_data.get("type")
        
        if resp_type in ("clarify", "answer"):
            # If the AI just wants to chat or ask a question, we print it directly.
            reply = response_data.get("content", "...")
            self.conversation_history.append({"role": "assistant", "content": reply})
            return reply
            
        elif resp_type == "single":
            # If the AI thinks a tool is needed (e.g., read Excel)
            tool = response_data.get("tool")
            args = response_data.get("arguments", {})
            
            # We execute the python function 
            tool_result = execute_tool(tool, args)
            
            # The AI hasn't spoken to the user yet. We feed the raw Excel data back to the AI without showing the user.
            self.conversation_history.append({"role": "assistant", "content": json.dumps(response_data)})
            self.conversation_history.append({"role": "user", "content": f"Tool '{tool}' returned: {json.dumps(tool_result, default=str)}. Now summarize this data to answer the original user query."})
            
            # Now we ask the AI to summarize those raw results and make them human-readable.
            synthesis_messages = [{"role": "system", "content": self.system_prompt}] + self.conversation_history
            final_resp = self._call_llm_with_retry(synthesis_messages)
            
            reply = final_resp.get("content", "Here are the results.")
            self.conversation_history.append({"role": "assistant", "content": reply})
            return reply
            
        elif resp_type == "multi":
            # Same as "single", but it triggers a loop of multiple tools consecutively 
            # (e.g., getting data from both Marketing and Real Estate tables).
            steps = response_data.get("steps", [])
            results_context = []
            
            for step in steps:
                t_name = step.get("tool")
                t_args = step.get("arguments", {})
                res = execute_tool(t_name, t_args)
                results_context.append({"tool": t_name, "result": res})
                
            # Feed the combined multi tool results back to the AI to summarize
            self.conversation_history.append({"role": "assistant", "content": json.dumps(response_data)})
            self.conversation_history.append({"role": "user", "content": f"Tool executions returned: {json.dumps(results_context, default=str)}. Please synthesize the final answer."})
            
            synthesis_messages = [{"role": "system", "content": self.system_prompt}] + self.conversation_history
            final_resp = self._call_llm_with_retry(synthesis_messages)
            
            reply = final_resp.get("content", "Here are the results.")
            self.conversation_history.append({"role": "assistant", "content": reply})
            return reply
            
        else:
            # Handles unexpected behavior
            return f"Error: The AI returned an unknown response type: {resp_type}"
