import logging
import sys

# Configure logger with both file and stderr handlers
LOGGER = logging.getLogger("puppeteer")
LOGGER.setLevel(logging.DEBUG)

# Prevent duplicate handlers if module is reloaded
if not LOGGER.handlers:
    # File handler - overwrites log file each run
    file_handler = logging.FileHandler('terminal_debug.log', mode='w')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

    # # Stderr handler - less verbose
    # stderr_handler = logging.StreamHandler(sys.stderr)
    # stderr_handler.setLevel(logging.DEBUG)
    # stderr_handler.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))

    LOGGER.addHandler(file_handler)
    # LOGGER.addHandler(stderr_handler)
