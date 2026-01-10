from pathlib import Path

from config.logger import LOGGER


class ApplyChange:
    def __init__(self, app):
        self.app = app

    def apply_pending_changes(self):
        if not self.app.pending_changes:
            self.app.update_chat("No changes to apply", "error")
            return
        
        # Show loading message
        self.app.update_chat("Applying changes to files...", "loading")
        
        try:
            # Handle line-based changes
            if 'changes' in self.app.pending_changes:
                changes = self.app.pending_changes['changes']
                LOGGER.debug(f"DEBUG: Applying {len(changes)} changes")
                applied_files = []
                
                for i, change in enumerate(changes, 1):
                    file_path = change['file_path']
                    new_content = change['new_content']
                    original_content = change['original_content']
                    action = change['action']
                    
                    # Convert relative path to absolute path based on working directory
                    if not Path(file_path).is_absolute():
                        absolute_file_path = self.app.working_dir / file_path
                    else:
                        absolute_file_path = Path(file_path)
                    
                    if action == 'create':
                        # Create new file
                        absolute_file_path.parent.mkdir(parents=True, exist_ok=True)
                        with open(absolute_file_path, 'w') as f:
                            f.write(new_content)
                        
                        lines_count = len(new_content.split('\n'))
                        applied_files.append(f"✅ CREATED: {file_path} ({lines_count} lines)")
                        
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
                
                # Show result
                result = f"🎉 Successfully applied {len(applied_files)} changes:\n\n" + "\n".join(applied_files)
                self.app.update_chat(result, "ai")

                
            else:
                # Handle legacy single file change
                file_path = self.app.pending_changes['file_path']
                new_content = self.app.pending_changes['new_content']
                original_content = self.app.pending_changes['original_content']
                
                # Convert relative path to absolute path based on working directory
                if not Path(file_path).is_absolute():
                    absolute_file_path = self.app.working_dir / file_path
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
                self.app.update_chat(f"✅ Changes applied! Backup: {backup_path.name}", "ai")
            
            # Clear pending changes
            self.app.pending_changes = None
            
        except Exception as e:
            # Show error
            self.app.update_chat(f"Error applying changes: {e}", "error")