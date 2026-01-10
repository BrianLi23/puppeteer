import asyncio
from pathlib import Path

from rich.text import Text 

from textual import on
from textual.app import App, ComposeResult
from textual.containers import Vertical
from textual.widgets import Footer, Input, LoadingIndicator, Select, Static
from textual.content import Content
from textual.worker import Worker, WorkerState

from config.logger import LOGGER
from services.ai_client import AgentClient
from services.apply_change import ApplyChange
from services.context import ContextBuilder
from services.indexer import Indexer
from hackyattacky2025.terminal.services.parser import Parser

class Terminal(App):
    CSS_PATH = "editor_template.tcss"
    
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("ctrl+c", "quit", "Quit"),
        ("escape", "cancel_changes", "Cancel"),
    ]

    def __init__(self, working_dir: str = "."):
        super().__init__()
        self.working_dir = Path(working_dir).resolve()
        self.context_file = ""
        self.pending_changes = None
        
        # Services
        self._agent_client = None
        self._apply_changes = None
        self._contextbuilder = None
        self._indexer = None
        self._parser = None
        
        self.files = self._discover_description_files()
    
    @property
    def agent_client(self):
        if self._agent_client is None:
            self._agent_client = AgentClient(self)
        return self._agent_client
    
    @property
    def apply_changes(self):
        if self._apply_changes is None:
            self._apply_changes = ApplyChange(self)
        return self._apply_changes
    
    @property
    def contextbuilder(self):
        if self._contextbuilder is None:
            self._contextbuilder = ContextBuilder(self)
        return self._contextbuilder
    
    @property
    def indexer(self):
        if self._indexer is None:
            self._indexer = Indexer(self)
        return self._indexer
    
    @property
    def parser(self):
        if self._parser is None:
            self._parser = Parser(self)
        return self._parser

    def _discover_description_files(self):

        files = []
        for path in self.working_dir.rglob("*"):
            parts = path.relative_to(self.working_dir).parts
            # Skip hidden directories
            if any(part.startswith('.') for part in parts[:-1]):
                continue
            if path.name.startswith('.'):  # Skip hidden files
                continue
            rel_path = path.relative_to(self.working_dir)
            # Select widget expects (display_text, value) tuples
            # We want to show relative path but use absolute path as value
            files.append((str(rel_path), str(path)))

        # Prioritize README-like files first, then alphabetical
        files.sort(key=lambda item: (0 if "readme" in item[0].lower() else 1, item[0].lower()))
        return files
    
    def compose(self) -> ComposeResult:
        with Vertical(classes="main"):
            # Header section
            with Vertical(id="header"):
                yield Static("🎭 Puppeteer", id="title")
                yield Static("The Application Runtime Assistant", id="subtitle")
                yield Static(
                    "Select the project description file to use as context for your requests, "
                    "then write your instructions for what you would like to agent to do during runtime.",
                    id="description",
                )
                yield Static(Content.from_markup("@Github: [@click=app.url('https://github.com/BrianLi23/puppeteer')]Repository[/] | @Devpost: [@click=app.url('https://devpost.com/software/puppeteer-7429qv')]Link[/]"), id="links")

            if self.files:
                yield Select(self.files, id="file_select", prompt="Select project description file...")
            else:
                yield Static("No files found")
                
            yield Static(id="chat", classes="main")
            yield LoadingIndicator(id="loading")
            
            yield Input(placeholder="Describe what you want me to do with your project...", id="input")
        
        yield Footer()
        
    @on(Select.Changed, "#file_select")
    def file_selected(self, event):
        if event.value:
            self.context_file = event.value
            try:
                path = Path(self.context_file)
                display_path = path.relative_to(self.working_dir) if path.is_absolute() else path
                self.update_chat(f"Selected context file: {display_path}", "ai")
            except Exception as exc:
                self.update_chat(f"Error selecting file: {exc}", "error")
    
    def action_cancel_changes(self) -> None:
        if self.pending_changes:
            self.pending_changes = None
            self.update_chat("Changes cancelled", "ai")
    
    def action_quit(self) -> None:
        self.exit()

    def action_url(self, url: str) -> None:
        import webbrowser

        webbrowser.open(url)
    
    def apply_code_changes(self):
        self.show_loading()
        
        # Run in background thread
        self.run_worker(self._apply_changes.apply_pending_changes(), exclusive=True)
    
    @on(Input.Submitted, "#input")
    def handle_input(self, event):
        user_request = event.value.strip()
        
        if not user_request:
            return
   
        event.input.value = ""
        self.show_loading()
        self.update_chat(f"You: {user_request}", "user") # Shows user message
        self.run_worker(self.process_user_request(user_request), exclusive=True)
         
        if user_request.lower() == 'apply':
            self.apply_code_changes()
            return
        
        elif user_request.lower() == 'cancel':
            self.pending_changes = None
            self.update_chat("Changes cancelled", "ai")
            return
        
        if not self.current_file:
            self.update_chat("Please select a project description file first", "error")
            return
    
    async def process_user_request(self, user_request: str):
        try:
            result = await asyncio.to_thread(self.agent_client.edit_project, user_request)
            self.hide_loading()
            
            if result == "NO_CHANGES_NEEDED":
                return
            
            self.update_chat(result, "ai")
            
        except Exception as e:
            self.hide_loading()
            self.update_chat(f"Error: {e}", "error")
    
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
    
    def show_loading(self):
        chat = self.query_one("#chat", Static)
        loading = self.query_one("#loading", LoadingIndicator)
        chat.styles.display = "none"
        loading.styles.display = "block"
    
    def hide_loading(self):
        chat = self.query_one("#chat", Static)
        loading = self.query_one("#loading", LoadingIndicator)
        loading.styles.display = "none"
        chat.styles.display = "block"
        
        
        
