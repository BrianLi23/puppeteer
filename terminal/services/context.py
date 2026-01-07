import os
from pathlib import Path
from typing import List
from config.logger import LOGGER

async def get_full_project_context(self) -> str:
    """Get context from all project files"""
    LOGGER.debug("DEBUG: Building full project context...")
    context_parts = []
    
    try:
        all_files = self.get_all_project_files()
        LOGGER.debug(f"DEBUG: Processing {len(all_files)} files for context")
        
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
                    LOGGER.debug(f"DEBUG: Truncated {file_path} from {original_length} to 150000 chars")

                context_parts.append(f"=== {file_path} ===\n{content}\n")
                
                if i % 10 == 0:  # Log progress every 10 files
                    LOGGER.debug(f"DEBUG: Processed {i+1}/{len(all_files)} files")
                
            except (UnicodeDecodeError, PermissionError):
                # Skip binary or inaccessible files
                context_parts.append(f"=== {file_path} ===\n[Binary or inaccessible file]\n")
                LOGGER.debug(f"DEBUG: Skipped binary/inaccessible file: {file_path}")
            except Exception as e:
                context_parts.append(f"=== {file_path} ===\n[Error reading file: {e}]\n")
                LOGGER.debug(f"DEBUG: Error reading {file_path}: {e}")
    except Exception as e:
        LOGGER.debug(f"DEBUG: Error in get_full_project_context: {e}")
    
    total_context = "\n".join(context_parts)
    LOGGER.debug(f"DEBUG: Built context with {len(total_context)} total characters")
    LOGGER.debug(f"DEBUG: Context includes {len(context_parts)} file sections")
    
    return total_context
    
    
    