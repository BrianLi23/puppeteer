from typing import Tuple, List
from pathlib import Path
from config.logger import LOGGER


class Indexer:
    def __init__(self, app):
        self.app = app

    def scan_project_files(self, working_dir: Path) -> List[Tuple[str, str]]:
        files = []
        try:
            # Recursively find all files in the working directory
            for file_path in working_dir.rglob("*"):
                if file_path.is_file():
                    # Ignore any file in a folder starting with a dot
                    parts = file_path.relative_to(working_dir).parts
                    if any(part.startswith('.') for part in parts[:-1]):
                        continue
                    # Skip hidden files, binary files, and common ignore patterns
                    if (not file_path.name.startswith('.') and 
                        file_path.suffix not in ['.pyc', '.exe', '.bin', '.so', '.dll'] and
                        '__pycache__' not in str(file_path) and
                        '.git' not in str(file_path)):
                        # Make path relative to working directory for display
                        rel_path = file_path.relative_to(working_dir)
                        files.append((str(rel_path), str(file_path)))
                        
        except Exception as e:
            # Debug: show error if any
            files.append((f"Error scanning: {e}", ""))
            pass
        
        # Debug: show count
        if files:
            files.insert(0, (f"Found {len(files)} files in {working_dir}", ""))
        else:
            files.append(("No files found", ""))
            
        return files

    def get_all_project_files(self) -> list:
        all_files = []
        LOGGER.debug(f"DEBUG: Scanning project files in {self.app.working_dir}...")
        
        try:
            for file_path in self.app.working_dir.rglob("*"):
                if file_path.is_file():
                    # Skip hidden files, binary files, and common ignore patterns
                    # Ignore any file in a folder starting with a dot
                    parts = file_path.relative_to(self.app.working_dir).parts
                    if any(part.startswith('.') for part in parts[:-1]):
                        continue
                    if (not file_path.name.startswith('.') and 
                        file_path.suffix not in ['.pyc', '.exe', '.bin', '.so', '.dll', '.backup'] and
                        '__pycache__' not in str(file_path) and
                        'terminal_debug.log' not in str(file_path)):
                        # Make path relative to working directory
                        rel_path = file_path.relative_to(self.app.working_dir)
                        all_files.append(str(rel_path))
                        
            LOGGER.debug(f"DEBUG: Found {len(all_files)} project files")
            for i, f in enumerate(all_files[:10]):  # Log first 10 files
                LOGGER.debug(f"  {i+1}. {f}")
            if len(all_files) > 10:
                LOGGER.debug(f"  ... and {len(all_files) - 10} more files")
                
        except Exception as e:
            LOGGER.debug(f"DEBUG: Error scanning files: {e}")
            
        return all_files