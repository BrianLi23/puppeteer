import importlib
from config.logger import LOGGER
import google.genai as genai
from google.genai import types
from dotenv import load_dotenv
import os
from terminal.terminal_prompt import terminal_prompt

async def call_mcp_edit_project(self, request: str) -> str:
    # Re-index all files before every AI call to get latest state
    LOGGER.debug("DEBUG: Re-indexing all project files...")
    context = await self.get_full_project_context()
    LOGGER.debug(f"DEBUG: Indexed {len(self.get_all_project_files())} files")
    
    # Simulate MCP call (in real implementation, this would use MCP client)
    return await self.simulate_mcp_project_call(request, context)

async def simulate_mcp_project_call(self, request: str, context: str) -> str:
    """Simulate MCP call for project-wide operations"""
        
    load_dotenv()
    
    # Setup Gemini
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return "❌ No API key found. Set GEMINI_API_KEY environment variable."
    
    client = genai.Client(api_key=api_key)
    
    # Read project description
    with open(self.current_file, 'r') as f:
        project_description = f.read()
    
    # Save user request to user_query.md file
    try:
        user_query_path = self.working_dir / "user_query.md"
        with open(user_query_path, "w") as f:
            f.write(f"{request}")
        LOGGER.debug(f"DEBUG: Saved user query to {user_query_path}: {request}")
    except Exception as e:
        LOGGER.debug(f"DEBUG: Error saving to user_query.md: {e}")
    
    # Build prompt for project-wide operations
    # Reload terminal_prompt module to get latest changes
    importlib.reload(terminal_prompt)
    prompt = terminal_prompt.TERMINAL_PROMPT + "\n\n"
    prompt += f"<project_description>\n{project_description}\n</project_description>\n\n"
    prompt += f"<project_files>\n{context}\n</project_files>\n\n"
    prompt += f"<user_request>\n{request}\n</user_request>"
    
    LOGGER.debug("=" * 50)
    LOGGER.debug("SENDING TO AI:")
    LOGGER.debug("=" * 50)
    LOGGER.debug(f"Prompt length: {len(prompt)} chars")
    LOGGER.debug("Last 500 chars of prompt:")
    LOGGER.debug(prompt[-500:])
    LOGGER.debug("=" * 50)
    
    # Call AI - Create chat session and send message
    chat_session = client.chats.create(
        model='gemini-2.5-flash',  # Use appropriate model
        config=types.GenerateContentConfig(
            system_instruction="You are an expert AI software engineer helping with code analysis and probing instrumentation."
        )
    )
    
    response = chat_session.send_message(prompt)
    ai_response = response.text
    
    LOGGER.debug("=" * 50)
    LOGGER.debug("AI RESPONSE RECEIVED:")
    LOGGER.debug("=" * 50)
    LOGGER.debug(f"Response length: {len(ai_response)} chars")
    LOGGER.debug("First 300 chars:")
    LOGGER.debug(ai_response[:300])
    LOGGER.debug("=" * 50)
    
    # Parse response and prepare changes using new before/after format
    return await self.parse_before_after_response(ai_response)
        