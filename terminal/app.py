import argparse
import sys
from pathlib import Path

from terminal import Terminal


def main():
    parser = argparse.ArgumentParser(description='Pupeeteer Terminal - AI-powered code editor')
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
