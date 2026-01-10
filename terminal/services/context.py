from pathlib import Path
from typing import List

from config.logger import LOGGER


class ContextBuilder:
    """Service for building project context"""
    
    def __init__(self, app):
        self.app = app

    def get_full_project_context(self) -> str:
        context_parts = []
        
        try:
            all_files = self.app.indexer.get_all_project_files()
            for i, file_path in enumerate(all_files):
                try:
                    # Convert relative path to absolute for file operations
                    absolute_path = self.app.working_dir / file_path
                    with open(absolute_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # Only limit very large files
                    original_length = len(content)
                    if len(content) > 150000: 
                        content = content[:150000] + f"\n... (file truncated, total length: {original_length} chars)"

                    context_parts.append(f"=== {file_path} ===\n{content}\n")
                    
                except (UnicodeDecodeError, PermissionError):
                    # Skip binary or inaccessible files
                    context_parts.append(f"=== {file_path} ===\n[Binary or inaccessible file]\n")
                except Exception as e:
                    context_parts.append(f"=== {file_path} ===\n[Error reading file: {e}]\n")
                    LOGGER.debug(f"DEBUG: Error reading {file_path}: {e}")
        except Exception as e:
            LOGGER.debug(f"DEBUG: Error in get_full_project_context: {e}")
        
        total_context = "\n".join(context_parts)
        return total_context
    
    
    