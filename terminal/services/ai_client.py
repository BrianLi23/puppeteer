import importlib
import os

import google.genai as genai
from google.genai import types
from dotenv import load_dotenv

import terminal_prompt
from config.logger import LOGGER

class AgentClient:
    def __init__(self, app):
        self.app = app
    
    def edit_project(self, request: str) -> str:
        
        load_dotenv()
        # Get full project context
        context = self.app.contextbuilder.get_full_project_context()
    
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            return " No API key found. Set GEMINI_API_KEY environment variable."
        
        client = genai.Client(api_key=api_key)
        
        with open(self.app.context_file, 'r') as f:
            project_description = f.read()
        
        # Save user request to user_query.md file, this will be read by AI runtime
        try:
            user_query_path = self.app.working_dir / "user_query.md"
            with open(user_query_path, "w") as f:
                f.write(f"{request}")
        except Exception as e:
            LOGGER.debug(f"DEBUG: Error saving to user_query.md: {e}")
        
        # importlib.reload(terminal_prompt)  # Ensure latest prompt content
        prompt = terminal_prompt.TERMINAL_PROMPT + "\n\n"
        prompt += f"<project_description>\n{project_description}\n</project_description>\n\n"
        prompt += f"<project_files>\n{context}\n</project_files>\n\n"
        prompt += f"<user_request>\n{request}\n</user_request>"

        chat_session = client.chats.create(
            model='gemini-2.5-flash',  # Use appropriate model
            config=types.GenerateContentConfig(
                system_instruction="You are an expert AI software engineer helping with code analysis and probing instrumentation."
            )
        )
        
        response = chat_session.send_message(prompt)
        ai_response = response.text
        
        return self.app.parser.parse_before_after_response(ai_response)
        