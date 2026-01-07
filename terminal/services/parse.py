

import re
from logging import LOGGER
    
def parse_file_sections(self, ai_response: str) -> list:
    sections = []
    
    LOGGER.debug("DEBUG: Starting file section parsing...")
    LOGGER.debug(f"DEBUG: Response length: {len(ai_response)} chars")
    
    # Simple pattern that matches the actual format from examples
    # Looks for "Original file (filename):" followed by content, then "Modified file (filename):" 
    pattern = r'Original file \(([^)]+)\):\s*\n(.*?)\n\n+Modified file \([^)]+\):\s*\n(.*?)(?=\n\n+Original file|\n\n+Example|\Z)'
    matches = re.findall(pattern, ai_response, re.DOTALL)
    
    LOGGER.debug(f"DEBUG: Regex found {len(matches)} matches")
    
    for i, match in enumerate(matches):
        filename = match[0].strip()
        original_content = match[1].strip()
        modified_content = match[2].strip()
        
        LOGGER.debug(f"DEBUG: Match {i+1}:")
        LOGGER.debug(f"  Raw filename: '{match[0]}'")
        LOGGER.debug(f"  Cleaned filename: '{filename}'")
        LOGGER.debug(f"  Original content length: {len(original_content)}")
        LOGGER.debug(f"  Modified content length: {len(modified_content)}")
        
        sections.append({
            'filename': filename,
            'original': original_content,
            'modified': modified_content
        })
    
    LOGGER.debug(f"DEBUG: Returning {len(sections)} sections")
    return sections

def generate_line_edits(self, original_content: str, modified_content: str) -> list:
    """Generate line-based edits by comparing original and modified content"""
    # For simplicity, just return a complete replacement
    # This is more reliable than complex diff parsing
    return [{
        'action': 'replace_all',
        'content': modified_content
    }]
    

async def parse_before_after_response(self, ai_response: str) -> str:
    """Parse before/after response format and prepare changes"""
    try:
        import os
        
        # Log the raw AI response
        LOGGER.debug("=" * 50)
        LOGGER.debug("RAW AI RESPONSE:")
        LOGGER.debug("=" * 50)
        LOGGER.debug(ai_response)
        LOGGER.debug("=" * 50)
        
        # Check for "no changes needed" response
        if "No changes needed" in ai_response:
            LOGGER.debug("DEBUG: No changes needed detected")
            return "NO_CHANGES_NEEDED"  # Special return value to handle silently
        
        # Extract file sections
        sections = self.parse_file_sections(ai_response)
        LOGGER.debug(f"DEBUG: Found {len(sections)} file sections")
        
        for i, section in enumerate(sections):
            LOGGER.debug(f"DEBUG: Section {i+1}:")
            LOGGER.debug(f"  Filename: {section['filename']}")
            LOGGER.debug(f"  Original length: {len(section['original'])} chars")
            LOGGER.debug(f"  Modified length: {len(section['modified'])} chars")
            LOGGER.debug(f"  Original preview: {section['original'][:100]}...")
            LOGGER.debug(f"  Modified preview: {section['modified'][:100]}...")
        
        if not sections:
            LOGGER.debug("DEBUG: No valid file changes found")
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