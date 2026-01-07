from config.logger import LOGGER
from pathlib import Path

async def apply_pending_changes(self):
    if not self.pending_changes:
        self.update_chat("No changes to apply", "error")
        return
    
    LOGGER.debug("DEBUG: Starting to apply changes...")
    LOGGER.debug(f"DEBUG: Pending changes keys: {list(self.pending_changes.keys())}")
    
    # Show loading message
    self.update_chat("Applying changes to files...", "loading")
    
    try:
        # Handle line-based changes
        if 'changes' in self.pending_changes:
            changes = self.pending_changes['changes']
            LOGGER.debug(f"DEBUG: Applying {len(changes)} changes")
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
                
                LOGGER.debug(f"DEBUG: Change {i}: {action} {file_path}")
                LOGGER.debug(f"DEBUG: Absolute path: {absolute_file_path}")
                LOGGER.debug(f"DEBUG: New content length: {len(new_content)} chars")
                LOGGER.debug(f"DEBUG: New content preview: {new_content[:100]}...")
                
                if action == 'create':
                    # Create new file
                    absolute_file_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(absolute_file_path, 'w') as f:
                        f.write(new_content)
                    
                    lines_count = len(new_content.split('\n'))
                    applied_files.append(f"✅ CREATED: {file_path} ({lines_count} lines)")
                    LOGGER.debug(f"DEBUG: Created {absolute_file_path} with {lines_count} lines")
                    
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
                    LOGGER.debug(f"DEBUG: Modified {absolute_file_path}: {old_lines} → {new_lines} lines")
            
            # Show result
            result = f"🎉 Successfully applied {len(applied_files)} changes:\n\n" + "\n".join(applied_files)
            self.update_chat(result, "ai")
            LOGGER.debug("DEBUG: All changes applied successfully")
            
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