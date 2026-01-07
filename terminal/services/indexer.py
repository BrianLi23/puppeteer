def scan_project_files(working_dir: Path) -> List[Tuple[str, str]]:
        """Find all files recursively in working directory"""
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