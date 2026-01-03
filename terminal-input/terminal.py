import logging
import os
import re
import sys
import argparse
import importlib
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

import terminal_prompt

# Setup debug logging to file
import logging
logging.basicConfig(
    filename='terminal_debug.log',
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filemode='w'  # Overwrite log file each time
)
debug_log = logging.getLogger(__name__)

def debug_print(*args, **kwargs):
    """Print to both stderr and log file"""
    message = ' '.join(str(arg) for arg in args)
    debug_log.info(message)
    print(message, file=sys.stderr, **kwargs)

class Terminal(App):
    async def on_mount(self) -> None:
        """Start background task to watch .md file for output."""
        self.md_file_path = self.working_dir / "report.md"
        self.last_line = None
        self.set_interval(1.0, self.watch_md_file)

    async def watch_md_file(self) -> None:
        """Read the last 8 lines from the .md file and print to the TUI if changed."""
        try:
            if self.md_file_path.exists():
                with open(self.md_file_path, "r", encoding="utf-8") as f:
                    lines = f.read().splitlines()
                last_lines = '\n'.join(lines[-8:]) if lines else ''
                if last_lines and last_lines != getattr(self, 'last_content', None):
                    self.last_content = last_lines
                    self.print_md_output(last_lines)
        except Exception as e:
            self.print_md_output(f"Error reading {self.md_file_path.name}: {e}")

    def print_md_output(self, content: str) -> None:
        """Overwrite the chat area with the latest .md file contents, styled nicely."""
        chat = self.query_one("#chat", Static)
        text = Text()
        text.append(f"📄 Object Tracing: \n", style="bold magenta")
        text.append(content, style="bold white on black")
        chat.update(text)
        chat.scroll_end()
        
    CSS_PATH = "editor_template.tcss"
    
    def __init__(self, working_dir: str = "."):
        super().__init__()
        self.working_dir = Path(working_dir).resolve()
        self.current_file = ""
        self.files = self.scan_files()
        self.pending_changes = None
        
        # Add key bindings
        self.title = f"MCP Minimal Editor - {self.working_dir} (Press Ctrl+C or q to quit)"
    
    def scan_files(self):
        """Find all files recursively in working directory"""
        files = []
        try:
            # Recursively find all files in the working directory
            for file_path in self.working_dir.rglob("*"):
                if file_path.is_file():
                    # Ignore any file in a folder starting with a dot
                    parts = file_path.relative_to(self.working_dir).parts
                    if any(part.startswith('.') for part in parts[:-1]):
                        continue
                    # Skip hidden files, binary files, and common ignore patterns
                    if (not file_path.name.startswith('.') and 
                        file_path.suffix not in ['.pyc', '.exe', '.bin', '.so', '.dll'] and
                        '__pycache__' not in str(file_path) and
                        '.git' not in str(file_path)):
                        # Make path relative to working directory for display
                        rel_path = file_path.relative_to(self.working_dir)
                        files.append((str(rel_path), str(file_path)))
        except Exception as e:
            # Debug: show error if any
            files.append((f"Error scanning: {e}", ""))
            pass
        
        # Debug: show count
        if files:
            files.insert(0, (f"Found {len(files)} files in {self.working_dir}", ""))
        else:
            files.append(("No files found", ""))
            
        return files
    
    def compose(self) -> ComposeResult:
        """Create minimal UI"""
        with Vertical(classes="main"):
            # File selector - now for any file to use as project description
            if self.files:
                yield Select(self.files, id="file_select", prompt="Select project description file (README, etc.)...")
            else:
                yield Static("No files found")
            
            # Chat area
            yield Static(id="chat", classes="main")
            
            # Input
            yield Input(placeholder="Describe what you want me to do with your project...", id="input")
        
        yield Footer()
    
    def action_quit(self) -> None:
        """Quit the application"""
        self.exit()
    
    def on_key(self, event) -> None:
        """Handle key presses"""
        if event.key == 'q' and not hasattr(self.focused, 'value'):  # Only if not in input field
            self.exit()
        elif event.key == 'ctrl+c':
            self.exit()
    
    @on(Select.Changed, "#file_select")
    def file_selected(self, event):
        """Project description file selected"""
        if event.value:
            self.current_file = event.value
            self.load_project_description()
    
    def load_project_description(self):
        """Load selected project description file and all project files"""
        try:
            with open(self.current_file, 'r') as f:
                content = f.read()
            
            # Show file loaded
            chat = self.query_one("#chat", Static)
            text = Text()
            text.append(f"📁 Project Description: {self.current_file}\n\n", style="bold cyan")
            
            # Show project description content
            lines = content.split('\n')[:10]
            preview = '\n'.join(lines)
            if len(content.split('\n')) > 10:
                preview += "\n..."
            
            text.append(preview, style="dim white")
            text.append(f"\n\n🔍 Loading all project files into context...", style="bold yellow")
            
            # Load all project files into context
            all_files = self.get_all_project_files()
            text.append(f"\n✅ Loaded {len(all_files)} files into context", style="bold green")
            
            chat.update(text)
            
        except Exception as e:
            self.update_chat(f"Error loading project: {e}", "error")
    
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
                debug_print("DEBUG: No changes needed, continuing silently")
                return
            
            # Show result for all other cases
            self.update_chat(result, "ai")
            
        except Exception as e:
            # Show error
            self.update_chat(f"Error: {e}", "error")
    
    async def call_mcp_edit_project(self, request: str) -> str:
        """Call MCP server to edit project based on request"""
        # Re-index all files before every AI call to get latest state
        debug_print("DEBUG: Re-indexing all project files...")
        context = await self.get_full_project_context()
        debug_print(f"DEBUG: Indexed {len(self.get_all_project_files())} files")
        
        # Simulate MCP call (in real implementation, this would use MCP client)
        return await self.simulate_mcp_project_call(request, context)
    
    async def simulate_mcp_project_call(self, request: str, context: str) -> str:
        """Simulate MCP call for project-wide operations"""
        try:
            # Import here to avoid import errors if google.genai not available
            try:
                import google.genai as genai
                from google.genai import types
            except ImportError as e:
                return f"❌ Google GenAI not available. Please install with: pip install google-genai\nError: {e}"
                
            import difflib
            import os
            from dotenv import load_dotenv
            
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
                debug_print(f"DEBUG: Saved user query to {user_query_path}: {request}")
            except Exception as e:
                debug_print(f"DEBUG: Error saving to user_query.md: {e}")
            
            # Build prompt for project-wide operations
            # Reload terminal_prompt module to get latest changes
            importlib.reload(terminal_prompt)
            prompt = terminal_prompt.TERMINAL_PROMPT + "\n\n"
            prompt += f"<project_description>\n{project_description}\n</project_description>\n\n"
            prompt += f"<project_files>\n{context}\n</project_files>\n\n"
            prompt += f"<user_request>\n{request}\n</user_request>"
            
            debug_print("=" * 50)
            debug_print("SENDING TO AI:")
            debug_print("=" * 50)
            debug_print(f"Prompt length: {len(prompt)} chars")
            debug_print("Last 500 chars of prompt:")
            debug_print(prompt[-500:])
            debug_print("=" * 50)
            
            # Call AI - Create chat session and send message
            chat_session = client.chats.create(
                model='gemini-2.5-flash',  # Use appropriate model
                config=types.GenerateContentConfig(
                    system_instruction="You are an expert AI software engineer helping with code analysis and probing instrumentation."
                )
            )
            
            response = chat_session.send_message(prompt)
            ai_response = response.text
            
            debug_print("=" * 50)
            debug_print("AI RESPONSE RECEIVED:")
            debug_print("=" * 50)
            debug_print(f"Response length: {len(ai_response)} chars")
            debug_print("First 300 chars:")
            debug_print(ai_response[:300])
            debug_print("=" * 50)
            
            # Parse response and prepare changes using new before/after format
            return await self.parse_before_after_response(ai_response)
                
        except Exception as e:
            return f"Error: {e}"
    
    def parse_file_sections(self, ai_response: str) -> list:
        """Extract file sections from AI response"""
        import re
        
        sections = []
        
        debug_print("DEBUG: Starting file section parsing...")
        debug_print(f"DEBUG: Response length: {len(ai_response)} chars")
        
        # Simple pattern that matches the actual format from examples
        # Looks for "Original file (filename):" followed by content, then "Modified file (filename):" 
        pattern = r'Original file \(([^)]+)\):\s*\n(.*?)\n\n+Modified file \([^)]+\):\s*\n(.*?)(?=\n\n+Original file|\n\n+Example|\Z)'
        matches = re.findall(pattern, ai_response, re.DOTALL)
        
        debug_print(f"DEBUG: Regex found {len(matches)} matches")
        
        for i, match in enumerate(matches):
            filename = match[0].strip()
            original_content = match[1].strip()
            modified_content = match[2].strip()
            
            debug_print(f"DEBUG: Match {i+1}:")
            debug_print(f"  Raw filename: '{match[0]}'")
            debug_print(f"  Cleaned filename: '{filename}'")
            debug_print(f"  Original content length: {len(original_content)}")
            debug_print(f"  Modified content length: {len(modified_content)}")
            
            sections.append({
                'filename': filename,
                'original': original_content,
                'modified': modified_content
            })
        
        debug_print(f"DEBUG: Returning {len(sections)} sections")
        return sections
    
    def generate_line_edits(self, original_content: str, modified_content: str) -> list:
        """Generate line-based edits by comparing original and modified content"""
        # For simplicity, just return a complete replacement
        # This is more reliable than complex diff parsing
        return [{
            'action': 'replace_all',
            'content': modified_content
        }]
    
    def assert_file_change_valid(self, file_path: str, original_content: str, new_content: str) -> dict:
        """Validate that the file change is safe to apply"""
        try:
            import os
            
            # Basic validation of new content
            if not new_content.strip():
                return {
                    'valid': False,
                    'reason': 'New content is empty'
                }
            
            # Convert relative path to absolute path based on working directory
            if not Path(file_path).is_absolute():
                absolute_file_path = self.working_dir / file_path
            else:
                absolute_file_path = Path(file_path)
            
            # Check if parent directory exists for new files
            if not absolute_file_path.exists():
                parent_dir = absolute_file_path.parent
                if parent_dir and not parent_dir.exists():
                    return {
                        'valid': False,
                        'reason': f'Parent directory does not exist: {parent_dir}'
                    }
            
            return {'valid': True}
            
        except Exception as e:
            return {
                'valid': False,
                'reason': f'Validation error: {e}'
            }
    
    async def parse_before_after_response(self, ai_response: str) -> str:
        """Parse before/after response format and prepare changes"""
        try:
            import os
            
            # Log the raw AI response
            debug_print("=" * 50)
            debug_print("RAW AI RESPONSE:")
            debug_print("=" * 50)
            debug_print(ai_response)
            debug_print("=" * 50)
            
            # Check for "no changes needed" response
            if "No changes needed" in ai_response:
                debug_print("DEBUG: No changes needed detected")
                return "NO_CHANGES_NEEDED"  # Special return value to handle silently
            
            # Extract file sections
            sections = self.parse_file_sections(ai_response)
            debug_print(f"DEBUG: Found {len(sections)} file sections")
            
            for i, section in enumerate(sections):
                debug_print(f"DEBUG: Section {i+1}:")
                debug_print(f"  Filename: {section['filename']}")
                debug_print(f"  Original length: {len(section['original'])} chars")
                debug_print(f"  Modified length: {len(section['modified'])} chars")
                debug_print(f"  Original preview: {section['original'][:100]}...")
                debug_print(f"  Modified preview: {section['modified'][:100]}...")
            
            if not sections:
                debug_print("DEBUG: No valid file changes found")
                return "❌ No valid file changes found in AI response."
            
            # Prepare changes
            prepared_changes = []
            validation_errors = []
            
            for section in sections:
                file_path = section['filename']
                original_content = section['original']
                modified_content = section['modified']
                
                # Validate the change
                validation = self.assert_file_change_valid(file_path, original_content, modified_content)
                
                if not validation['valid']:
                    validation_errors.append(f"{file_path}: {validation['reason']}")
                    continue
                
                # Generate line edits for display
                edits = self.generate_line_edits(original_content, modified_content)
                
                prepared_changes.append({
                    'file_path': file_path,
                    'original_content': original_content,
                    'new_content': modified_content,
                    'action': 'create' if not os.path.exists(file_path) else 'modify',
                    'edits': edits
                })
            
            if validation_errors:
                error_msg = "❌ Validation errors:\n" + "\n".join(validation_errors)
                if not prepared_changes:
                    return error_msg
                else:
                    error_msg += f"\n\n⚠️ Proceeding with {len(prepared_changes)} valid changes..."
            
            if prepared_changes:
                # Store all pending changes
                self.pending_changes = {
                    'changes': prepared_changes,
                    'analysis': f"Parsed {len(sections)} file changes from AI response"
                }
                
                result = f"📋 PROPOSED CHANGES ({len(prepared_changes)} file(s)):\n\n"
                
                for i, change in enumerate(prepared_changes, 1):
                    file_path = change['file_path']
                    original_content = change['original_content']
                    new_content = change['new_content']
                    action = change['action']
                    
                    if action == 'create':
                        result += f"📝 {i}. CREATE: {file_path}\n"
                        result += f"   Content preview ({len(new_content)} chars):\n"
                        # Show first few lines
                        preview_lines = new_content.split('\n')[:5]
                        for line in preview_lines:
                            result += f"   + {line}\n"
                        if len(new_content.split('\n')) > 5:
                            result += f"   + ... ({len(new_content.split('\n')) - 5} more lines)\n"
                    else:
                        result += f"✏️ {i}. MODIFY: {file_path}\n"
                        
                        # Show diff preview
                        original_lines = original_content.split('\n')
                        new_lines = new_content.split('\n')
                        
                        result += f"   Changes: {len(original_lines)} → {len(new_lines)} lines\n"
                        
                        # Show a few key differences
                        import difflib
                        diff = list(difflib.unified_diff(original_lines, new_lines, lineterm='', n=2))
                        diff_preview = []
                        for line in diff:
                            if line.startswith('---') or line.startswith('+++') or line.startswith('@@'):
                                continue
                            if line.startswith('-'):
                                diff_preview.append(f"   - {line[1:]}")
                            elif line.startswith('+'):
                                diff_preview.append(f"   + {line[1:]}")
                            if len(diff_preview) >= 6:  # Limit preview
                                break
                        
                        if diff_preview:
                            result += "\n".join(diff_preview[:6])
                            if len(diff_preview) > 6:
                                result += f"\n   ... ({len(diff_preview) - 6} more changes)"
                        else:
                            result += "   Complete file replacement"
                    
                    result += "\n\n"
                
                if validation_errors:
                    result = error_msg + "\n\n" + result
                
                result += "💡 Type 'apply' to save all changes or 'cancel' to discard"
                return result
            else:
                return "❌ No valid changes found after validation."
                
        except Exception as e:
            return f"❌ Error parsing response: {e}\n\nRaw response:\n{ai_response[:500]}..."
    
    def get_all_project_files(self) -> list:
        """Get list of all project files"""
        all_files = []
        debug_print(f"DEBUG: Scanning project files in {self.working_dir}...")
        
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
                        
            debug_print(f"DEBUG: Found {len(all_files)} project files")
            for i, f in enumerate(all_files[:10]):  # Log first 10 files
                debug_print(f"  {i+1}. {f}")
            if len(all_files) > 10:
                debug_print(f"  ... and {len(all_files) - 10} more files")
                
        except Exception as e:
            debug_print(f"DEBUG: Error scanning files: {e}")
            
        return all_files
    
    async def get_full_project_context(self) -> str:
        """Get context from all project files"""
        debug_print("DEBUG: Building full project context...")
        context_parts = []
        
        try:
            all_files = self.get_all_project_files()
            debug_print(f"DEBUG: Processing {len(all_files)} files for context")
            
            for i, file_path in enumerate(all_files):
                try:
                    # Convert relative path to absolute for file operations
                    absolute_path = self.working_dir / file_path
                    with open(absolute_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # Only limit very large files
                    original_length = len(content)
                    if len(content) > 150000: 
                        content = content[:150000] + f"\n... (file truncated, total length: {original_length} chars)"
                        debug_print(f"DEBUG: Truncated {file_path} from {original_length} to 150000 chars")

                    context_parts.append(f"=== {file_path} ===\n{content}\n")
                    
                    if i % 10 == 0:  # Log progress every 10 files
                        debug_print(f"DEBUG: Processed {i+1}/{len(all_files)} files")
                    
                except (UnicodeDecodeError, PermissionError):
                    # Skip binary or inaccessible files
                    context_parts.append(f"=== {file_path} ===\n[Binary or inaccessible file]\n")
                    debug_print(f"DEBUG: Skipped binary/inaccessible file: {file_path}")
                except Exception as e:
                    context_parts.append(f"=== {file_path} ===\n[Error reading file: {e}]\n")
                    debug_print(f"DEBUG: Error reading {file_path}: {e}")
        except Exception as e:
            debug_print(f"DEBUG: Error in get_full_project_context: {e}")
        
        total_context = "\n".join(context_parts)
        debug_print(f"DEBUG: Built context with {len(total_context)} total characters")
        debug_print(f"DEBUG: Context includes {len(context_parts)} file sections")
        
        return total_context
    
    async def apply_pending_changes(self):
        """Apply all pending line-based changes"""
        if not self.pending_changes:
            self.update_chat("No changes to apply", "error")
            return
        
        debug_print("DEBUG: Starting to apply changes...")
        debug_print(f"DEBUG: Pending changes keys: {list(self.pending_changes.keys())}")
        
        # Show loading message
        self.update_chat("Applying changes to files...", "loading")
        
        try:
            # Handle line-based changes
            if 'changes' in self.pending_changes:
                changes = self.pending_changes['changes']
                debug_print(f"DEBUG: Applying {len(changes)} changes")
                applied_files = []
                
                for i, change in enumerate(changes, 1):
                    file_path = change['file_path']
                    new_content = change['new_content']
                    original_content = change['original_content']
                    action = change['action']
                    
                    # Convert relative path to absolute path based on working directory
                    if not Path(file_path).is_absolute():
                        absolute_file_path = self.working_dir / file_path
                    else:
                        absolute_file_path = Path(file_path)
                    
                    debug_print(f"DEBUG: Change {i}: {action} {file_path}")
                    debug_print(f"DEBUG: Absolute path: {absolute_file_path}")
                    debug_print(f"DEBUG: New content length: {len(new_content)} chars")
                    debug_print(f"DEBUG: New content preview: {new_content[:100]}...")
                    
                    if action == 'create':
                        # Create new file
                        absolute_file_path.parent.mkdir(parents=True, exist_ok=True)
                        with open(absolute_file_path, 'w') as f:
                            f.write(new_content)
                        
                        lines_count = len(new_content.split('\n'))
                        applied_files.append(f"✅ CREATED: {file_path} ({lines_count} lines)")
                        debug_print(f"DEBUG: Created {absolute_file_path} with {lines_count} lines")
                        
                    elif action == 'modify':
                        # Create backup for existing file
                        backup_path = absolute_file_path.with_suffix(absolute_file_path.suffix + '.backup')
                        with open(backup_path, 'w') as f:
                            f.write(original_content)
                        
                        # Write new content
                        with open(absolute_file_path, 'w') as f:
                            f.write(new_content)
                        
                        old_lines = len(original_content.split('\n'))
                        new_lines = len(new_content.split('\n'))
                        applied_files.append(f"✅ MODIFIED: {file_path} ({old_lines} → {new_lines} lines, backup: {backup_path.name})")
                        debug_print(f"DEBUG: Modified {absolute_file_path}: {old_lines} → {new_lines} lines")
                
                # Show result
                result = f"🎉 Successfully applied {len(applied_files)} changes:\n\n" + "\n".join(applied_files)
                self.update_chat(result, "ai")
                debug_print("DEBUG: All changes applied successfully")
                
            else:
                # Handle legacy single file change
                file_path = self.pending_changes['file_path']
                new_content = self.pending_changes['new_content']
                original_content = self.pending_changes['original_content']
                
                # Convert relative path to absolute path based on working directory
                if not Path(file_path).is_absolute():
                    absolute_file_path = self.working_dir / file_path
                else:
                    absolute_file_path = Path(file_path)
                
                # Create backup
                backup_path = absolute_file_path.with_suffix(absolute_file_path.suffix + '.backup')
                with open(backup_path, 'w') as f:
                    f.write(original_content)
                
                # Write new content
                with open(absolute_file_path, 'w') as f:
                    f.write(new_content)
                
                # Show result
                self.update_chat(f"✅ Changes applied! Backup: {backup_path.name}", "ai")
            
            # Clear pending changes
            self.pending_changes = None
            
        except Exception as e:
            # Show error
            self.update_chat(f"Error applying changes: {e}", "error")
    
    def update_chat(self, text: str, message_type: str = "info"):
        """Update chat area with new text"""
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


def main():
    parser = argparse.ArgumentParser(description='MCP Terminal - AI-powered code editor')
    parser.add_argument('--path', '-p', 
                        default='.',
                        help='Path to the directory to index and work with (default: current directory)')
    
    args = parser.parse_args()
    
    # Verify the path exists
    working_path = Path(args.path)
    if not working_path.exists():
        print(f"Error: Path '{args.path}' does not exist", file=sys.stderr)
        sys.exit(1)
    
    if not working_path.is_dir():
        print(f"Error: Path '{args.path}' is not a directory", file=sys.stderr)
        sys.exit(1)
    
    app = Terminal(working_dir=str(working_path))
    app.run()


if __name__ == "__main__":
    main()
