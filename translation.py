# translation.py
import os
import sys
import json
import locale # <--- Import the locale module

# Import necessary components from other refactored modules
import config
from utils import get_resource_path

# --- Module-level variables ---
translations = {}
# current_language will be set by initialize_translations now
current_language = config.DEFAULT_LANG # Keep a default fallback just in case

# --- Functions ---
def load_translations(lang_code):
    """Loads translations for the given language code into the global 'translations' dict."""
    global translations
    # Ensure lang_dir path is correct (it's relative to the original script location)
    # Assuming LANG_DIR in config is already set correctly for resource finding
    relative_filepath = os.path.join(os.path.basename(config.LANG_DIR), f"{lang_code}.json")
    filepath = get_resource_path(relative_filepath) # Use utils to find it in _MEIPASS or script dir
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            translations = json.load(f)
        print(f"Successfully loaded translations for: {lang_code}")
        return True
    except FileNotFoundError:
        print(f"ERROR: Language file not found: {filepath}")
        if lang_code != config.DEFAULT_LANG:
             print(f"Falling back to {config.DEFAULT_LANG}.")
             if load_translations(config.DEFAULT_LANG):
                 return True
             else:
                 translations = {}
                 return False
        else:
             translations = {}
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
            print(f"ERROR: Failed to set language to {lang_code}, even after fallback attempt.")
            current_language = lang_code # Reflect the attempted language
            return False
    else:
        print(f"Warning: Unsupported language code '{lang_code}'. Language not changed.")
        return False

def _(key, **kwargs):
    """Gets the translated string for a key, falling back to the key itself."""
    message = translations.get(str(key), f"[{key}]")
    if kwargs:
        try:
            message = message.format(**kwargs)
        except KeyError as e:
            print(f"Warning: Missing placeholder {e} in translation for key '{key}'")
        except Exception as e:
            print(f"Warning: Error formatting translation for key '{key}' with args {kwargs}: {e}")
            message = translations.get(str(key), f"[{key}]")
    return message

# --- Modified Initialization Function ---
def initialize_translations():
    """
    Detects system language and loads translations, falling back to default.
    Sets the initial current_language.
    """
    global current_language # We are setting the global variable
    detected_lang = None
    try:
        # Get the default locale tuple (e.g., ('en_US', 'cp1252'), ('de_DE', 'UTF-8'))
        # locale.setlocale(locale.LC_ALL, "") # Sometimes needed, but getdefaultlocale often works without it
        locale_info = locale.getdefaultlocale()
        if locale_info and locale_info[0]:
            # Extract the language part (e.g., 'en' from 'en_US', 'de' from 'de_DE')
            detected_lang = locale_info[0].split('_')[0].lower()
            print(f"Detected system language code: {detected_lang}")
        else:
            print("Could not detect system locale information.")
    except Exception as e:
        # Catch potential errors during locale detection (e.g., unsupported locale)
        print(f"Warning: Error detecting system locale: {e}")

    # Determine the target language
    target_lang = config.DEFAULT_LANG # Start with the fallback default
    if detected_lang and detected_lang in config.SUPPORTED_LANGS:
        # If detected language is supported, use it
        target_lang = detected_lang
        print(f"System language '{target_lang}' is supported. Setting as initial language.")
    else:
        # If detected language is not supported or detection failed, use default
        if detected_lang:
            print(f"System language '{detected_lang}' is not supported. Falling back to default '{config.DEFAULT_LANG}'.")
        else:
            print(f"Falling back to default language '{config.DEFAULT_LANG}'.")

    # Load the determined target language
    print(f"Initializing translations with language: {target_lang}")
    if load_translations(target_lang):
        current_language = target_lang # Update the global variable successfully
    else:
         # If loading the target language failed, try the ultimate fallback (config.DEFAULT_LANG)
         print(f"FATAL: Could not load initial language file '{target_lang}'. Attempting fallback '{config.DEFAULT_LANG}'.")
         if target_lang != config.DEFAULT_LANG:
             if load_translations(config.DEFAULT_LANG):
                 current_language = config.DEFAULT_LANG # Fallback succeeded
             else:
                 # Both detected/initial and fallback failed
                 print(f"FATAL: Could not load fallback language file '{config.DEFAULT_LANG}'. UI text will be missing.")
                 current_language = config.DEFAULT_LANG # Set to default code anyway
                 translations = {} # Ensure translations are empty
         else:
             # Default language itself failed
             print(f"FATAL: Could not load default language file '{config.DEFAULT_LANG}'. UI text will be missing.")
             current_language = config.DEFAULT_LANG
             translations = {}

# --- Initial Load ---
# No initial call here, called explicitly from gui.py startup
