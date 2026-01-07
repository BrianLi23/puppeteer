from pathlib import Path

import google.genai as genai
from google.genai import types
import difflib
from dotenv import load_dotenv
from rich.syntax import Syntax
from rich.text import Text

from textual import on
from textual.app import App, ComposeResult
from textual.containers import Vertical
from textual.widgets import Footer, Header, Input, Log, Select, Static

from services.indexer import get_all_project_files
from services.fs import load_file
from services.ai_client import process_request
from services.applier import apply_changes

from terminal_prompt import terminal_prompt
from config.logger import LOGGER

class Terminal(App):
    def __init__(self, working_dir: str = "."):
        super().__init__()
        self.working_dir = Path(working_dir).resolve()
        self.current_file = ""
        self.pending_changes = None
        
        # Add key bindings
        self.title = f"MCP Minimal Editor - {self.working_dir} (Press Ctrl+C or q to quit)"
    
    def compose(self) -> ComposeResult:
        with Vertical(classes="main"):
            if self.files:
                yield Select(self.files, id="file_select", prompt="Select project description file (README, etc.)...")
            else:
                yield Static("No files found")
            yield Static(id="chat", classes="main")
            yield Input(placeholder="Describe what you want me to do with your project...", id="input")
        
        yield Footer()
        
    @on(Select.Changed, "#file_select")
    def file_selected(self, event):
        """Project description file selected"""
        if event.value:
            self.current_file = event.value
            self.load_project_description()
    
    def action_quit(self) -> None:
        """Quit the application"""
        self.exit()
    
    def on_key(self, event) -> None:
        """Handle key presses"""
        if event.key == 'q' and not hasattr(self.focused, 'value'):  # Only if not in input field
            self.exit()
        elif event.key == 'ctrl+c':
            self.exit()
    
    @on(Input.Submitted, "#input")
    async def handle_input(self, event):
        """Process user input"""
        request = event.value.strip()
        if not request:
            return
            
        # Clear input
        event.input.value = ""
        
        # Handle commands
        if request.lower() == 'apply':
            await self.apply_pending_changes()
            return
        elif request.lower() == 'cancel':
            self.pending_changes = None
            self.update_chat("Changes cancelled", "ai")
            return
        
        if not self.current_file:
            self.update_chat("Please select a project description file first", "error")
            return
        
        # Show user request
        self.update_chat(f"You: {request}", "user")
        
        # Show loading message
        self.update_chat("Re-indexing project files and analyzing...", "loading")
        
        try:
            # Call MCP server
            result = await self.call_mcp_edit_project(request)
            
            # Handle special "No changes needed" case silently
            if result == "NO_CHANGES_NEEDED":
                # Just continue silently - user query already saved to user_query.md
                LOGGER.debug("DEBUG: No changes needed, continuing silently")
                return
            
            # Show result for all other cases
            self.update_chat(result, "ai")
            
        except Exception as e:
            # Show error
            self.update_chat(f"Error: {e}", "error")
    
    def get_all_project_files(self) -> list:
        """Get list of all project files"""
        all_files = []
        LOGGER.debug(f"DEBUG: Scanning project files in {self.working_dir}...")
        
        try:

            for file_path in self.working_dir.rglob("*"):
                if file_path.is_file():
                    # Skip hidden files, binary files, and common ignore patterns
                    # Ignore any file in a folder starting with a dot
                    parts = file_path.relative_to(self.working_dir).parts
                    if any(part.startswith('.') for part in parts[:-1]):
                        continue
                    if (not file_path.name.startswith('.') and 
                        file_path.suffix not in ['.pyc', '.exe', '.bin', '.so', '.dll', '.backup'] and
                        '__pycache__' not in str(file_path) and
                        'terminal_debug.log' not in str(file_path)):
                        # Make path relative to working directory
                        rel_path = file_path.relative_to(self.working_dir)
                        all_files.append(str(rel_path))
                        
            LOGGER.debug(f"DEBUG: Found {len(all_files)} project files")
            for i, f in enumerate(all_files[:10]):  # Log first 10 files
                LOGGER.debug(f"  {i+1}. {f}")
            if len(all_files) > 10:
                LOGGER.debug(f"  ... and {len(all_files) - 10} more files")
                
        except Exception as e:
            LOGGER.debug(f"DEBUG: Error scanning files: {e}")
            
        return all_files
    
    def update_chat(self, text: str, message_type: str = "info"):
        chat = self.query_one("#chat", Static)
        current = chat.renderable if hasattr(chat, 'renderable') and chat.renderable else Text()
        
        if not isinstance(current, Text):
            current = Text()
        
        # Add spacing
        if str(current):
            current.append("\n")
        
        # Style based on type
        if message_type == "user":
            current.append(f"💬 {text}", style="bold blue")
        elif message_type == "ai":
            current.append(f"🤖 {text}", style="bold green")
        elif message_type == "loading":
            current.append(f"⏳ {text}", style="italic cyan")
        elif message_type == "error":
            current.append(f"❌ {text}", style="bold red")
        else:
            current.append(text, style="white")
        
        chat.update(current)
        chat.scroll_end()
        
        
        
