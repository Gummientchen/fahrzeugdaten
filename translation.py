# translation.py
import os
import sys
import json

# Import necessary components from other refactored modules
import config
from utils import get_resource_path

# --- Module-level variables ---
translations = {}
current_language = config.DEFAULT_LANG

# --- Functions ---
def load_translations(lang_code):
    """Loads translations for the given language code into the global 'translations' dict."""
    global translations # We are modifying the global dict
    relative_filepath = os.path.join(config.LANG_DIR, f"{lang_code}.json")
    filepath = get_resource_path(relative_filepath) # Use utils
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            translations = json.load(f)
        print(f"Successfully loaded translations for: {lang_code}")
        return True
    except FileNotFoundError:
        print(f"ERROR: Language file not found: {filepath}")
        # Try falling back to default language if the requested one fails
        if lang_code != config.DEFAULT_LANG:
             print(f"Falling back to {config.DEFAULT_LANG}.")
             # Only clear translations if the fallback *also* fails
             if load_translations(config.DEFAULT_LANG):
                 return True # Fallback succeeded
             else:
                 translations = {} # Clear if default also failed
                 return False
        else:
             translations = {} # Clear if default failed initially
             return False
    except json.JSONDecodeError as e:
        print(f"ERROR: Failed to parse language file {filepath}: {e}")
        translations = {}
        return False
    except Exception as e:
        print(f"ERROR: Unexpected error loading language file {filepath}: {e}")
        translations = {}
        return False

def set_language(lang_code):
    """Sets the current language for the application and loads its translations."""
    global current_language
    if lang_code in config.SUPPORTED_LANGS:
        if load_translations(lang_code):
            current_language = lang_code
            return True
        else:
            # load_translations handles fallback, if it returns False, something is wrong
            print(f"ERROR: Failed to set language to {lang_code}, even after fallback attempt.")
            # Keep the previous language if loading fails? Or stick with potentially failed default?
            # Let's stick with the failed attempt's state (likely empty translations or failed default)
            current_language = lang_code # Reflect the attempted language
            return False
    else:
        print(f"Warning: Unsupported language code '{lang_code}'. Language not changed.")
        return False

def _(key, **kwargs):
    """Gets the translated string for a key, falling back to the key itself."""
    # Note: This simplified version doesn't handle the 'lang' override from the old GUI version.
    # If per-call override is needed, it needs reimplementation here.
    message = translations.get(str(key), f"[{key}]") # Use str(key) for safety, fallback to [key]
    if kwargs:
        try:
            message = message.format(**kwargs)
        except KeyError as e:
            print(f"Warning: Missing placeholder {e} in translation for key '{key}'")
        except Exception as e:
            # Catch other formatting errors (like wrong type for specifier)
            print(f"Warning: Error formatting translation for key '{key}' with args {kwargs}: {e}")
            # Fallback to message without formatting if error occurs
            message = translations.get(str(key), f"[{key}]")
    return message

def initialize_translations():
    """Loads the default translations when the application starts."""
    print(f"Initializing translations with default language: {config.DEFAULT_LANG}")
    if not load_translations(config.DEFAULT_LANG):
         print("FATAL: Could not load default language file. UI text will be missing.")
         # In a real app, might show an error dialog or exit here.

# --- Initial Load ---
# Load default language when this module is first imported
# initialize_translations()
# Let's call this explicitly from gui.py startup instead to ensure order.
