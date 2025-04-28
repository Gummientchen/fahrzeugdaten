# utils.py
import re
import os
import sys

def clean_sql_identifier(name):
    """Cleans a string to be a valid SQL identifier (table/column name)."""
    if not isinstance(name, str): return ""
    name = re.sub(r'[ /.\-+()]+', '_', name)
    # Specific replacements needed *before* stripping underscore if they create leading/trailing ones
    name = name.replace('ET_THC_NOx', 'ET_THC_NOx') # Keep as is
    name = name.replace('ZT_THC_NOx', 'ZT_THC_NOx') # Keep as is
    name = name.strip('_')
    if name and name[0].isdigit(): name = '_' + name
    return name

def create_normalized_table_name(base_name):
    """Creates a pluralized table name for normalized columns."""
    clean_name = clean_sql_identifier(base_name)
    if not clean_name: return None
    # Simple pluralization rules (adjust if needed)
    if clean_name.endswith('e'): return f"{clean_name}n"
    elif clean_name.endswith('s'): return f"{clean_name}es"
    else: return f"{clean_name}s"

def get_resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        # Not running in a bundle, use the script's directory
        base_path = os.path.abspath(os.path.dirname(__file__))

    return os.path.join(base_path, relative_path)

