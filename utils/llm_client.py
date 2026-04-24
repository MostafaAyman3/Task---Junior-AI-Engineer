import os
import json
import logging
from dotenv import load_dotenv
from openai import OpenAI
from google import genai
from google.genai import types

# load_dotenv() reads the secret keys inside the .env file and makes them available globally.
load_dotenv()

# Set up simple logging so we can print warning messages to the console if a model fails.
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load API keys from the environment variables safely.
GPT_OSS_KEY = os.getenv("GPT_OSS_120B_API_KEY", "")
GEMINI_KEY = os.getenv("GEMINI_3_FLASH_API_KEY", "")

def _convert_messages_to_gemini(messages_open_ai: list):
    """
    Since Groq uses the 'OpenAI format' (role: user/system/assistant), and Gemini uses 
    its own unique 'Google GenAI format' (parts, contents), we need to translate the messages 
    so Gemini can understand them before we send the request.
    """
    gemini_contents = []
    system_instruction = ""
    
    for msg in messages_open_ai:
        if msg["role"] == "system":
            # Gemini handles the system prompts (instructions) separately from the chat history.
            system_instruction += msg["content"] + "\n"
        else:
            # Convert 'assistant' -> 'model', and keep 'user' -> 'user'
            role = "user" if msg["role"] == "user" else "model"
            gemini_contents.append(
                types.Content(
                    role=role,
                    parts=[types.Part.from_text(text=msg["content"])]
                )
            )
            
    return gemini_contents, system_instruction

def query_llm_with_fallback(messages: list) -> str:
    """
    This is the core network function. It tries its best to get an answer from the AI.
    It takes an important strategy called "Active/Passive Fallback":
    1. First, try to send the request to Groq. 
    2. If Groq crashes, times out, or has high traffic (rate limits), do NOT crash the app.
    3. Instead, catch the error quietly, and "fallback" to the Gemini models to ensure the user gets an answer.
    """
    errors = []
    
    # 1. GROQ ATTEMPTS (Our Primary AI Provider)
    if GPT_OSS_KEY and not GPT_OSS_KEY.startswith("your_"):
        try:
            groq_client = OpenAI(
                api_key=GPT_OSS_KEY,
                base_url="https://api.groq.com/openai/v1",
            )
            
            # List of Groq models to try (Primary -> Fallbacks)
            groq_models = ["openai/gpt-oss-120b"]
            
            for model in groq_models:
                try:
                    logger.info(f"[LLM Client] Attempting Groq model: {model}")
                    response = groq_client.chat.completions.create(
                        model=model,
                        messages=messages,
                        temperature=0.0, # Temperature 0 means we want deterministic, less creative JSON output
                        response_format={"type": "json_object"} # Forces the AI to return raw JSON instead of text
                    )
                    return response.choices[0].message.content
                except Exception as e:
                    # If the specific model fails, record the error and continue to the next model
                    logger.warning(f"[LLM Client] Groq model ({model}) failed: {str(e)}")
                    errors.append(f"Groq ({model}): {str(e)}")
                    continue # Try next Groq model
                    
        except Exception as client_err:
            logger.warning(f"[LLM Client] Groq setup failed: {str(client_err)}")
            errors.append(f"Groq Setup: {str(client_err)}")

    # 2. GEMINI ATTEMPTS (Our Backup AI Provider)
    logger.info("[LLM Client] Groq attempts exhausted. Falling back to Gemini.")
    if GEMINI_KEY and not GEMINI_KEY.startswith("your_"):
        try:
            # Convert messages before sending them to Gemini
            gemini_contents, system_instruction = _convert_messages_to_gemini(messages)
            gemini_client = genai.Client(api_key=GEMINI_KEY)
            config = types.GenerateContentConfig(
                temperature=0.0,
                system_instruction=system_instruction if system_instruction else None
            )
            
            # List of Gemini models to try in order of preference. If one fails, try the next.
            gemini_models = ["gemini-3-flash-preview", "gemini-3.1-flash-lite-preview", "gemini-2.5-flash-lite", "gemini-1.5-flash"]
            
            for model in gemini_models:
                try:
                    logger.info(f"[LLM Client] Attempting Gemini model: {model}")
                    response = gemini_client.models.generate_content(
                        model=model,
                        contents=gemini_contents,
                        config=config
                    )
                    return response.text
                except Exception as e:
                    logger.warning(f"[LLM Client] Gemini model ({model}) failed: {str(e)}")
                    errors.append(f"Gemini ({model}): {str(e)}")
                    continue # Try next Gemini model
                    
        except Exception as fallback_err:
            logger.error(f"[LLM Client] Gemini setup failed: {str(fallback_err)}")
            errors.append(f"Gemini Setup: {str(fallback_err)}")

    # 3. TOTAL FAILURE
    # If BOTH Groq and Gemini completely went down, we return a safe JSON string back to our code
    # telling it to show the user a friendly "Services are down" message without crashing the whole Python app.
    logger.error("[LLM Client] ALL MODELS FAILED.")
    
    error_summary = "\n".join(errors)
    return json.dumps({
        "type": "answer",
        "content": f"I apologize, but my backend AI services are currently unavailable. Errors encountered:\n{error_summary}"
    })
