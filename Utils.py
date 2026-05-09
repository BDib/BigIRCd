# Utils.py
import sys
import os
import string

def get_base_path(is_resource=True) -> str:
    """
    is_resource=True: Returns temp path for MOTD/Images (PyInstaller _MEIPASS) 
    or the script directory.
    is_resource=False: Returns the folder where the .exe sits or the script directory 
    (for the DB/MOTD editing).
    """
    # 1. Check if running as a PyInstaller bundle
    if getattr(sys, 'frozen', False):
        if is_resource:
            # Internal bundled resources (_MEIPASS)
            return getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(sys.executable)))
        # Path where the .exe actually lives
        return os.path.dirname(os.path.abspath(sys.executable))
    
    # 2. Running in an interpreter instance
    # Returns the directory of Utils.py (the project root)
    return os.path.dirname(os.path.abspath(__file__))

def resource_path(relative_path: str) -> str:
    """Used for read-only files like motd.txt."""
    return os.path.join(get_base_path(is_resource=True), relative_path)

def data_path(relative_path: str) -> str:
    """Used for files that need to PERSIST (like the database) next to the script/EXE."""
    return os.path.join(get_base_path(is_resource=False), relative_path)

def irc_lower(s: bytes) -> bytes:
    """Standardized IRC case folding."""
    trans = bytes.maketrans(
        (string.ascii_lowercase.upper() + "[]\\^").encode(), 
        (string.ascii_lowercase + "{}|~").encode()
    )
    return s.translate(trans)