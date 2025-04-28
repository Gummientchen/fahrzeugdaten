# gui.py
import sqlite3
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, font
import threading
import os
import sys
import json # Import json module
from datetime import datetime
import requests

# --- Constants ---
LANG_DIR = "lang"
DEFAULT_LANG = "en" # Default language
SUPPORTED_LANGS = {
    "en": "English",
    "de": "Deutsch",
    "fr": "Français",  # Added French
    "it": "Italiano"   # Added Italian
}

# --- Global translation dictionary and current language ---
translations = {}
current_language = DEFAULT_LANG

def get_resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        # Not running in a bundle, use the script's directory
        base_path = os.path.abspath(os.path.dirname(__file__))

    return os.path.join(base_path, relative_path)

# --- Translation Loading Function (MODIFIED) ---
def load_translations(lang_code):
    global translations, current_language
    # MODIFIED: Use get_resource_path
    relative_filepath = os.path.join(LANG_DIR, f"{lang_code}.json")
    filepath = get_resource_path(relative_filepath)

    # Add print for debugging
    print(f"Attempting to load language file from: {filepath}")

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            translations = json.load(f)
        current_language = lang_code
        print(f"Successfully loaded translations for: {lang_code}")
        return True
    except FileNotFoundError:
        print(f"ERROR: Language file not found: {filepath}") # Show the path it tried
        if lang_code != "en": # Try falling back to English
             print("Falling back to English.")
             return load_translations("en")
        translations = {} # Clear translations if even English fails
        return False
    except json.JSONDecodeError as e:
        print(f"ERROR: Failed to parse language file {filepath}: {e}")
        translations = {}
        return False
    except Exception as e:
        print(f"ERROR: Unexpected error loading language file {filepath}: {e}")
        translations = {}
        return False


# --- Translation Helper Function (MODIFIED) ---
def _(key, **kwargs):
    """Gets the translated string for a key, falling back to the key itself."""
    lookup_translations = translations
    if 'lang' in kwargs:
        lang_code_override = kwargs.pop('lang')
        temp_translations = {}
        # MODIFIED: Use get_resource_path for override path
        relative_filepath = os.path.join(LANG_DIR, f"{lang_code_override}.json")
        filepath = get_resource_path(relative_filepath)
        try:
            # Add print for debugging override path
            print(f"Attempting to load override language file from: {filepath}")
            with open(filepath, 'r', encoding='utf-8') as f:
                temp_translations = json.load(f)
            lookup_translations = temp_translations
            print(f"Successfully loaded override language: {lang_code_override}")
        except Exception as e:
            # Fallback to current translations if override file fails
            print(f"Warning: Failed to load override language file '{filepath}': {e}")
            pass # lookup_translations remains the global 'translations'

    message = lookup_translations.get(key, f"[{key}]") # Get message or show [key] if missing
    if kwargs:
        try:
            message = message.format(**kwargs) # Fill placeholders
        except KeyError as e:
            print(f"Warning: Missing placeholder {e} in translation for key '{key}'")
        except Exception as e:
            print(f"Warning: Error formatting translation for key '{key}': {e}") # Catch other formatting errors
    return message



# --- Load initial translations ---
load_translations(DEFAULT_LANG)


# --- Attempt to import functions from other scripts ---
script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

try:
    from importer import main as run_import_main
    from search import (
        search_by_tg_code, DATABASE_PATH, DISPLAY_ORDER_WITH_DIVIDERS,
        DIVIDER_MARKER, UNITS_MAP, KW_TO_PS, HOMOLOGATIONSDATUM_INPUT_FORMAT,
        HOMOLOGATIONSDATUM_OUTPUT_FORMAT, ANTRIEB_MAP, TREIBSTOFF_MAP,
        OMIT_COLUMNS_CLEANED, clean_sql_identifier
    )
    from export import create_pdf as export_single_pdf, EXPORT_DIR as EXPORT_DIR_SINGLE
    from compare import (
        get_formatted_car_data, generate_comparison_pdf,
        EXPORT_DIR as EXPORT_DIR_COMPARE
    )
except ImportError as e:
    print(f"ERROR: Failed to import required modules: {e}")
    print("Please ensure importer.py, search.py, export.py, and compare.py are in the same directory.")
    print("Also ensure dependencies (fpdf2, requests) are installed: pip install fpdf2 requests")
    try:
        root_err = tk.Tk()
        root_err.withdraw()
        messagebox.showerror(_("msg_title_import_error"), f"Failed to import required modules: {e}\n\nPlease ensure required .py files are present and dependencies (fpdf2, requests) are installed.")
        root_err.destroy()
    except tk.TclError: pass
    sys.exit(1)
except Exception as e:
     print(f"ERROR: An unexpected error occurred during imports: {e}")
     try:
        root_err = tk.Tk()
        root_err.withdraw()
        messagebox.showerror(_("msg_title_import_error"), f"An unexpected error occurred during imports: {e}")
        root_err.destroy()
     except tk.TclError: pass
     sys.exit(1)


# --- GUI Application Class ---

class VehicleDataApp:
    def __init__(self, root):
        # --- FIX: Assign root to self.root FIRST ---
        self.root = root
        # --- End FIX ---

        self.waiting_dialog = None
        self.import_running_at_startup = False
        self.progress_var = tk.DoubleVar()
        self.progress_bar = None
        self.progress_label_var = tk.StringVar()
        self.current_search_data = None
        # self.previous_translations = {} # Keep for menu items like Exit/Import - Not strictly needed with index 0 assumption

        # --- Styling ---
        self.style = ttk.Style()
        self.style.theme_use('clam')
        default_font = font.nametofont("TkDefaultFont")
        default_font.configure(size=10)
        self.root.option_add("*Font", default_font)

        # --- Menu Bar ---
        self.menubar = tk.Menu(self.root)
        self.root.config(menu=self.menubar)

        # --- Create the menus THEMSELVES once ---
        self.file_menu = tk.Menu(self.menubar, tearoff=0)
        self.data_menu = tk.Menu(self.menubar, tearoff=0)
        self.language_menu = tk.Menu(self.menubar, tearoff=0)

        # --- Populate the menus (commands, radiobuttons) ---
        # Use placeholders that will be updated by _update_ui_text
        self.file_menu.add_command(label="TEMP_EXIT", command=self.root.quit)
        self.data_menu.add_command(label="TEMP_IMPORT", command=self._run_import_thread)
        self.selected_language_var = tk.StringVar(value=current_language)
        for code, name in SUPPORTED_LANGS.items():
             self.language_menu.add_radiobutton(
                 label=name, variable=self.selected_language_var, value=code,
                 command=lambda c=code: self.change_language(c)
             )

        # --- Main Frame ---
        main_frame = ttk.Frame(root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # --- Compare Section ---
        self.compare_frame = ttk.LabelFrame(main_frame, text="TEMP_COMPARE", padding="10") # Placeholder
        self.compare_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(5,0))
        compare_input_frame = ttk.Frame(self.compare_frame)
        compare_input_frame.pack(fill=tk.X)
        self.compare_tg_codes_label = ttk.Label(compare_input_frame, text="TEMP_COMPARE_LABEL") # Placeholder
        self.compare_tg_codes_label.pack(side=tk.LEFT, padx=5)
        self.compare_tg_codes_entry = ttk.Entry(compare_input_frame, width=40)
        self.compare_tg_codes_entry.pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)
        self.compare_button = ttk.Button(self.compare_frame, text="TEMP_COMPARE_BTN", command=self._compare_vehicles) # Placeholder
        self.compare_button.pack(pady=5)

        # --- Search/Export Section ---
        self.search_frame = ttk.LabelFrame(main_frame, text="TEMP_SEARCH", padding="10") # Placeholder
        self.search_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, pady=(0,5))
        search_input_frame = ttk.Frame(self.search_frame)
        search_input_frame.pack(side=tk.TOP, fill=tk.X)
        self.tg_code_search_label = ttk.Label(search_input_frame, text="TEMP_TG_CODE") # Placeholder
        self.tg_code_search_label.pack(side=tk.LEFT, padx=5)
        self.search_tg_code_entry = ttk.Entry(search_input_frame, width=20)
        self.search_tg_code_entry.pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)
        search_button_frame = ttk.Frame(self.search_frame)
        search_button_frame.pack(side=tk.TOP, fill=tk.X, pady=5)
        self.search_button = ttk.Button(search_button_frame, text="TEMP_SEARCH_BTN", command=self._search_vehicle) # Placeholder
        self.search_button.pack(side=tk.LEFT, padx=5)
        self.export_button = ttk.Button(search_button_frame, text="TEMP_EXPORT_BTN", command=self._export_vehicle_pdf, state=tk.DISABLED) # Placeholder
        self.export_button.pack(side=tk.LEFT, padx=5)
        self.search_results_text = scrolledtext.ScrolledText(self.search_frame, height=10, width=80, wrap=tk.WORD, state=tk.DISABLED, font=("Courier New", 9))
        self.search_results_text.pack(side=tk.TOP, fill=tk.BOTH, expand=True, pady=(0,5))

        # --- Status Bar ---
        self.status_var = tk.StringVar()
        self.status_bar = ttk.Label(root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W, padding="2 5")
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        # --- Apply initial UI text (which includes building the menubar) ---
        self._update_ui_text() # This will now call _build_menubar


    # --- NEW METHOD to build/rebuild menubar cascades ---
    def _build_menubar(self):
        """Deletes and rebuilds the main menubar cascades with current translations."""
        # Delete existing cascades first (if any)
        # Using index('end') is safer than hardcoding range
        try:
            last_index = self.menubar.index(tk.END)
            # Iterate backwards to avoid index shifting issues when deleting
            for i in range(last_index, -1, -1):
                try:
                    self.menubar.delete(i)
                except tk.TclError as e:
                    # This might happen if the menu is already empty, usually safe to ignore
                    # print(f"Info: Could not delete menu cascade at index {i} (might be empty): {e}") # Optional debug
                    pass # Ignore errors during deletion, menu might be empty
        except tk.TclError:
             # Menu might be completely empty, index(tk.END) fails
             pass # Safe to ignore

        # Add cascades with current translations
        self.menubar.add_cascade(label=_("file_menu"), menu=self.file_menu)
        self.menubar.add_cascade(label=_("data_menu"), menu=self.data_menu)
        self.menubar.add_cascade(label=_("language_menu"), menu=self.language_menu)
        # print(f"DEBUG: Rebuilt menubar with: '{_('file_menu')}', '{_('data_menu')}', '{_('language_menu')}'") # Optional debug


    # --- Update UI Text (MODIFIED) ---
    def _update_ui_text(self):
        """Updates static text elements in the UI based on current language."""
        self.root.title(_("window_title"))

        # --- Rebuild Menubar Cascade Labels ---
        # This is the reliable way to update the top-level menu labels
        self._build_menubar()

        # --- Update ITEMS WITHIN menus ---
        # Assume Exit is always the first item (index 0) in file_menu
        try:
            self.file_menu.entryconfig(0, label=_("exit_menu"))
            # print(f"DEBUG: Updated Exit menu item using index 0") # Optional debug
        except tk.TclError as e:
             print(f"Warning: Could not find/update 'Exit' menu item at index 0: {e}")

        # Assume Import is always the first item (index 0) in data_menu
        try:
            self.data_menu.entryconfig(0, label=_("import_menu"))
            # print(f"DEBUG: Updated Import menu item using index 0") # Optional debug
        except tk.TclError as e:
             print(f"Warning: Could not find/update 'Import' menu item at index 0: {e}")

        # Update LabelFrames
        self.search_frame.config(text=_("search_export_frame"))
        self.compare_frame.config(text=_("compare_frame"))

        # Update Labels
        self.tg_code_search_label.config(text=_("tg_code_label"))
        self.compare_tg_codes_label.config(text=_("compare_tg_codes_label"))

        # Update Buttons
        self.search_button.config(text=_("search_button"))
        self.export_button.config(text=_("export_pdf_button"))
        self.compare_button.config(text=_("compare_button"))

        # Update Status Bar (initial state or safe default)
        current_status = self.status_var.get()
        # Check if status is empty, a placeholder, or the 'Ready' message in any known language
        is_default_status = (
            not current_status or
            current_status.startswith("[") or
            any(current_status == _("status_ready", lang=lang_code) for lang_code in SUPPORTED_LANGS)
        )
        if is_default_status:
             self.status_var.set(_("status_ready"))
        # Otherwise, leave the current status (e.g., "Importing...") as is

        # Update Waiting Dialog Text (if open)
        if self.waiting_dialog is not None and self.waiting_dialog.winfo_exists():
             self.waiting_dialog.title(_("waiting_dialog_title"))
             # Find the main label within the dialog frame
             for widget in self.waiting_dialog.winfo_children():
                 if isinstance(widget, ttk.Frame):
                     for sub_widget in widget.winfo_children():
                         # Check if it's a Label and not the progress percentage label
                         if isinstance(sub_widget, ttk.Label) and hasattr(sub_widget, 'cget'):
                             current_text = sub_widget.cget("text")
                             is_progress_label = "%" in current_text or "..." in current_text
                             if not is_progress_label:
                                 label_text = _("waiting_dialog_init") if self.import_running_at_startup else _("waiting_dialog_update")
                                 sub_widget.config(text=label_text)
                                 break # Found and updated the main label
                     break # Stop searching after the main frame


    # --- Change Language ---
    def change_language(self, lang_code):
        """Loads new translations and updates the UI text elements."""
        # No need to store previous_translations for cascade labels with rebuild approach
        # self.previous_translations = translations.copy()

        if load_translations(lang_code):
            # Update the UI using the new translations
            self._update_ui_text() # This will now trigger _build_menubar
        else:
            # Use translated error title
            messagebox.showerror(_("msg_title_import_error"), f"Could not load language: {lang_code}")


    # --- Helper Methods ---
    def _update_status(self, message_key, **kwargs):
        translated_message = _(message_key, **kwargs)
        self.root.after(0, self.status_var.set, translated_message)

    def _show_error(self, title_key, message_key, **kwargs):
        title = _(title_key); message = _(message_key, **kwargs)
        self.root.after(0, messagebox.showerror, title, message)

    def _show_info(self, title_key, message_key, **kwargs):
        title = _(title_key); message = _(message_key, **kwargs)
        self.root.after(0, messagebox.showinfo, title, message)

    # --- Waiting Dialog ---
    def _show_waiting_dialog(self):
        if self.waiting_dialog is not None and self.waiting_dialog.winfo_exists(): return
        self.waiting_dialog = tk.Toplevel(self.root)
        self.waiting_dialog.title(_("waiting_dialog_title")) # Use translation
        self.waiting_dialog.geometry("350x150"); self.waiting_dialog.resizable(False, False)
        self.waiting_dialog.transient(self.root); self.waiting_dialog.protocol("WM_DELETE_WINDOW", lambda: None) # Prevent closing
        # Center dialog relative to root window
        self.root.update_idletasks() # Ensure root window dimensions are up-to-date
        root_x = self.root.winfo_rootx(); root_y = self.root.winfo_rooty()
        root_w = self.root.winfo_width(); root_h = self.root.winfo_height()
        dialog_w = 350; dialog_h = 150
        x = root_x + (root_w // 2) - (dialog_w // 2); y = root_y + (root_h // 2) - (dialog_h // 2)
        x, y = int(x), int(y) # Ensure integer coordinates
        self.waiting_dialog.geometry(f"+{x}+{y}") # Position the dialog

        dialog_frame = ttk.Frame(self.waiting_dialog, padding="10"); dialog_frame.pack(expand=True, fill=tk.BOTH)
        label_text = _("waiting_dialog_init") if self.import_running_at_startup else _("waiting_dialog_update")
        wait_label = ttk.Label(dialog_frame, text=label_text, justify=tk.CENTER); wait_label.pack(pady=(0, 10))
        self.progress_bar = ttk.Progressbar(dialog_frame, orient='horizontal', mode='determinate', variable=self.progress_var, maximum=100.0)
        self.progress_bar.pack(fill=tk.X, padx=10, pady=5)
        initial_progress_text = _("progress_percent", percentage=0.0); self.progress_label_var.set(initial_progress_text)
        progress_text_label = ttk.Label(dialog_frame, textvariable=self.progress_label_var); progress_text_label.pack(pady=(0, 5))
        self.progress_var.set(0.0)
        self.waiting_dialog.grab_set(); self.root.update_idletasks() # Make modal

    def _close_waiting_dialog(self):
        if self.waiting_dialog is not None and self.waiting_dialog.winfo_exists():
            self.waiting_dialog.grab_release(); self.waiting_dialog.destroy()
            self.waiting_dialog = None; self.progress_bar = None

    # --- Progress Update Callback ---
    def _update_progress(self, current_row, total_rows):
        if total_rows > 0:
            percentage = min((current_row / total_rows) * 100.0, 100.0)
            # Format with one decimal place using the translated string
            progress_text = _("progress_percent", percentage=percentage)
            self.root.after(0, self.progress_var.set, percentage)
            self.root.after(0, self.progress_label_var.set, progress_text)
        else:
            # Indeterminate progress
            progress_text = _("progress_ellipsis") # Use translated ellipsis text
            self.root.after(0, self.progress_var.set, 0.0) # Or maybe set mode to indeterminate if desired
            self.root.after(0, self.progress_label_var.set, progress_text)
            # Optionally switch progress bar mode
            # if self.progress_bar: self.root.after(0, self.progress_bar.config, {'mode': 'indeterminate'})


    # --- Import Handling ---
    def _run_import_thread(self, is_startup=False):
        self.import_running_at_startup = is_startup
        # Find index using current language text before disabling
        # Assuming Import is always the first item in the Data menu (index 0)
        try:
            self.data_menu.entryconfig(0, state=tk.DISABLED)
        except tk.TclError:
            print("Warning: Could not disable Import menu item at index 0.")


        self.search_button.config(state=tk.DISABLED); self.export_button.config(state=tk.DISABLED); self.compare_button.config(state=tk.DISABLED)
        self._update_status("status_import_starting")
        self._show_waiting_dialog()
        self.progress_var.set(0.0); self.progress_label_var.set(_("progress_percent", percentage=0.0))
        if self.progress_bar: self.root.after(0, self.progress_bar.config, {'mode': 'determinate'}) # Ensure determinate mode
        import_thread = threading.Thread(target=self._execute_import, daemon=True); import_thread.start()

    def _execute_import(self):
        import_success = False
        try:
            status_key = "status_import_running"; self._update_status(status_key)
            run_import_main(progress_callback=self._update_progress)
            # Check if DB exists *after* import attempt
            if os.path.exists(DATABASE_PATH):
                 import_success = True; self._update_status("status_import_success")
                 # Only show popup if not during startup
                 if not self.import_running_at_startup:
                     self._show_info("msg_title_import_complete", "msg_import_complete")
            else:
                 # If DB still doesn't exist, it's an error, even if importer didn't raise exception
                 raise FileNotFoundError(f"Database file '{DATABASE_PATH}' not found after import attempt.")

        except FileNotFoundError as e: self._update_status("status_import_error_file", error=e); self._show_error("msg_title_import_error", "msg_import_file_not_found", error=e)
        except sqlite3.Error as e: self._update_status("status_import_error_db", error=e); self._show_error("msg_title_import_error", "msg_import_db_error", error=e)
        except requests.exceptions.RequestException as e: self._update_status("status_import_error_download", error=e); self._show_error("msg_title_import_error", "msg_import_download_error", error=e)
        except IOError as e: self._update_status("status_import_error_io", error=e); self._show_error("msg_title_import_error", "msg_import_io_error", error=e)
        except OSError as e: self._update_status("status_import_error_os", error=e); self._show_error("msg_title_import_error", "msg_import_os_error", error=e)
        except Exception as e: self._update_status("status_import_error_unknown", error=e); self._show_error("msg_title_import_error", "msg_import_unknown_error", error=e)
        finally:
            # Ensure UI updates happen on the main thread
            self.root.after(0, self._finalize_import, import_success)

    def _finalize_import(self, import_successful):
        self._close_waiting_dialog()
        db_now_exists = os.path.exists(DATABASE_PATH)
        self.progress_var.set(0.0); self.progress_label_var.set("") # Clear progress text

        # Assuming Import is always the first item in the Data menu (index 0)
        try:
            self.data_menu.entryconfig(0, state=tk.NORMAL) # Always re-enable import after attempt
        except tk.TclError:
             print("Warning: Could not enable Import menu item at index 0.")


        if db_now_exists:
            self._update_status("status_ready")
            self.search_button.config(state=tk.NORMAL)
            # Enable export only if there's current data displayed
            if self.current_search_data:
                self.export_button.config(state=tk.NORMAL)
            else:
                self.export_button.config(state=tk.DISABLED)
            self.compare_button.config(state=tk.NORMAL)
        else:
            # If DB still doesn't exist after import attempt
            self._update_status("status_db_missing_fail", db_path=DATABASE_PATH)
            self.search_button.config(state=tk.DISABLED)
            self.export_button.config(state=tk.DISABLED)
            self.compare_button.config(state=tk.DISABLED)
            # Show error only if it failed during startup import
            if self.import_running_at_startup:
                self._show_error("msg_title_db_error", "msg_db_init_failed", db_path=DATABASE_PATH)

        self.import_running_at_startup = False # Reset flag

    # --- Search Handling ---
    def _search_vehicle(self):
        tg_code = self.search_tg_code_entry.get().strip()
        if not tg_code:
            self._show_error("msg_title_input_missing", "msg_input_tg_code_search")
            return

        self._update_status("status_searching", code=tg_code)
        self.search_results_text.config(state=tk.NORMAL)
        self.search_results_text.delete('1.0', tk.END)
        self.export_button.config(state=tk.DISABLED) # Disable export until search succeeds
        self.current_search_data = None # Clear previous search data

        try:
            result_row, normalized_mapping = search_by_tg_code(tg_code)
            if result_row:
                self.current_search_data = (result_row, normalized_mapping) # Store data
                display_text = self._format_search_result(result_row)
                self.search_results_text.insert(tk.END, display_text)
                self._update_status("status_search_found", code=tg_code)
                self.export_button.config(state=tk.NORMAL) # Enable export
            else:
                # Use translated message for no results
                self.search_results_text.insert(tk.END, _("search_results_none", code=tg_code))
                self._update_status("status_search_not_found", code=tg_code)
        except sqlite3.Error as e:
            self._update_status("status_search_db_error", error=e)
            # Use translated error message
            self.search_results_text.insert(tk.END, _("search_results_db_error", error=e))
            self._show_error("msg_title_search_error", "msg_search_db_error", error=e)
        except Exception as e:
            self._update_status("status_search_error", error=e)
            # Use translated error message
            self.search_results_text.insert(tk.END, _("search_results_unknown_error", error=e))
            self._show_error("msg_title_search_error", "msg_search_unknown_error", error=e)
        finally:
            self.search_results_text.config(state=tk.DISABLED) # Make read-only again

    # --- _format_search_result (FINAL FIX) ---
    def _format_search_result(self, result_row):
        """Formats the search result using translations."""
        lines = []
        lines.append(_("divider_text")) # Use translated divider

        # --- FINAL FIX: Use dictionary access consistently ---
        try:
            # Access header values using dictionary-style square brackets.
            # Keys must match the column names/aliases returned by the search query.
            tg_code_val = result_row['TG_Code'] # Query returns 'TG_Code' (underscore) via e.*
            marke_val = result_row['Marke']     # Query returns 'Marke' (no underscore) via alias
            typ_val = result_row['Typ']         # Query returns 'Typ' (no underscore) via e.*
        except KeyError as e:
            # This block executes if any of the expected keys ('TG_Code', 'Marke', 'Typ')
            # are missing from the result_row, which indicates a problem upstream
            # (e.g., in the search query or database structure).
            print(f"ERROR: Missing expected header key in result_row: {e}. Displaying N/A.")
            # Assign 'N/A' as fallback values if a key is missing
            tg_code_val = 'N/A'
            marke_val = 'N/A'
            typ_val = 'N/A'
            # You might want to log the full result_row here for debugging:
            # print(f"Problematic result_row keys: {result_row.keys()}")
        # --- END FINAL FIX ---

        # Use translated header format
        lines.append(_("search_results_header", code=tg_code_val, make=marke_val, model=typ_val))
        lines.append(_("divider_text")) # Use translated divider

        available_columns = result_row.keys()
        # Get the cleaned TG_Code column name once for use in the loop check below
        tg_code_db_col = clean_sql_identifier('TG-Code') # Result: 'TG_Code'

        # --- Loop for remaining fields ---
        for item_name in DISPLAY_ORDER_WITH_DIVIDERS:
            if item_name == DIVIDER_MARKER:
                lines.append(_("divider_text"))
                continue

            # --- Skip header columns already displayed ---
            if item_name == 'TG-Code' or item_name == tg_code_db_col or item_name == 'Marke' or item_name == 'Typ':
                 continue

            # --- Logic for finding and formatting value for the body ---
            value = None
            display_name = item_name # Use original name from DISPLAY_ORDER as the label
            cleaned_col_name_check = clean_sql_identifier(item_name)
            access_key = None

            # Determine the correct key to access result_row for this item_name
            if item_name in available_columns:
                access_key = item_name
            elif cleaned_col_name_check in available_columns:
                access_key = cleaned_col_name_check
            else:
                 continue # Skip if neither key is found

            # Access the value using the determined key (dictionary-style)
            try:
                 value = result_row[access_key]
            except KeyError:
                 # Should not happen if access_key was found in available_columns, but safety check
                 print(f"Warning: Unexpected KeyError accessing '{access_key}' for item '{item_name}'. Skipping.")
                 continue

            # Check if column should be omitted
            if cleaned_col_name_check in OMIT_COLUMNS_CLEANED:
                continue

            # --- Formatting logic (Date, (leer), Translations, Units, PS) ---
            # (This part remains unchanged from the previous correct version)
            display_value = ""
            is_leistung = (cleaned_col_name_check == 'Leistung')
            is_antrieb = (cleaned_col_name_check == 'Antrieb')
            is_treibstoff = (cleaned_col_name_check == 'Treibstoff')

            if cleaned_col_name_check == 'Homologationsdatum':
                if value:
                    try:
                        date_obj = datetime.strptime(str(value), HOMOLOGATIONSDATUM_INPUT_FORMAT)
                        display_value = date_obj.strftime(HOMOLOGATIONSDATUM_OUTPUT_FORMAT)
                    except (ValueError, TypeError):
                        display_value = f"{value} (format?)"
            elif isinstance(value, str) and value == '(leer)':
                display_value = ""
            elif value is not None:
                display_value = str(value)

            if is_antrieb and display_value:
                display_value = ANTRIEB_MAP.get(display_value, display_value)
            elif is_treibstoff and display_value:
                display_value = TREIBSTOFF_MAP.get(display_value, display_value)

            cleaned_col_name_for_units = cleaned_col_name_check
            if is_leistung and display_value:
                try:
                    kw_str = display_value.split(' ')[0]
                    kw_value_float = float(kw_str)
                    ps_value = kw_value_float * KW_TO_PS
                    ps_value_formatted = f"{ps_value:.1f}"
                    display_value = f"{kw_str} kW / {ps_value_formatted} PS"
                except (ValueError, TypeError):
                    display_value = f"{display_value} kW (Invalid)"
            elif display_value and cleaned_col_name_for_units in UNITS_MAP and not is_leistung:
                display_value = f"{display_value} {UNITS_MAP[cleaned_col_name_for_units]}"

            # Add the formatted line to the output
            lines.append(f"{item_name:<25}: {display_value}")

        lines.append(_("divider_text"))
        return "\n".join(lines)



    # --- Export Handling (MODIFIED) ---
    def _export_vehicle_pdf(self):
        if not self.current_search_data:
            self._show_error("msg_title_export_error", "msg_export_no_data")
            return

        result_row, norm_map = self.current_search_data
        # Safely get TG code for status message using dictionary access
        try:
            # FIX: Access using dictionary-style square brackets instead of .get()
            tg_code = result_row['TG_Code']
        except KeyError:
            # Fallback if 'TG_Code' key is unexpectedly missing (shouldn't happen if search worked)
            print("Warning: 'TG_Code' key not found in search result data during export. Using 'UNKNOWN_TGCODE'.")
            tg_code = 'UNKNOWN_TGCODE'


        self._update_status("status_exporting", code=tg_code)
        try:
            os.makedirs(EXPORT_DIR_SINGLE, exist_ok=True) # Ensure export dir exists

            # Create filename (logic remains the same)
            # Use the tg_code variable obtained above
            cleaned_name_part = clean_sql_identifier(tg_code)
            safe_filename_part = cleaned_name_part.lstrip('_') # Avoid leading underscore if TG code starts with number
            base_filename = f"{safe_filename_part}.pdf"
            full_pdf_path = os.path.join(EXPORT_DIR_SINGLE, base_filename)

            # Call the export function from export.py
            # (export.py's create_pdf function already uses dictionary access, which is good)
            export_single_pdf(result_row, norm_map, full_pdf_path)

            self._update_status("status_export_success", path=full_pdf_path)
            self._show_info("msg_title_export_success", "msg_export_success", path=full_pdf_path)

        except OSError as e:
            self._update_status("status_export_folder_error", error=e)
            self._show_error("msg_title_export_error", "msg_export_folder_error", path=EXPORT_DIR_SINGLE, error=e)
        except Exception as e:
            self._update_status("status_export_error", error=e)
            self._show_error("msg_title_export_error", "msg_export_unknown_error", error=e)


    # --- Compare Handling ---
    def _compare_vehicles(self):
        tg_codes_str = self.compare_tg_codes_entry.get().strip()
        if not tg_codes_str:
            self._show_error("msg_title_input_missing", "msg_input_tg_code_compare")
            return

        # Split and clean input codes
        tg_codes_input = [code.strip() for code in tg_codes_str.split(',') if code.strip()]

        # Validate number of codes
        if not (2 <= len(tg_codes_input) <= 3):
            self._show_error("msg_title_compare_error", "msg_compare_invalid_input")
            return

        codes_str = ', '.join(tg_codes_input) # For status message
        self._update_status("status_comparing", codes=codes_str)

        all_car_data_formatted = []
        valid_tg_codes_for_header = []
        found_data = False

        try:
            # Fetch data for each code
            for tg_code in tg_codes_input:
                self._update_status("status_compare_fetching", code=tg_code)
                # Use the function from compare.py
                formatted_data = get_formatted_car_data(tg_code)
                all_car_data_formatted.append(formatted_data) # Append even if None to keep order
                valid_tg_codes_for_header.append(tg_code) # Keep original code for header
                if formatted_data:
                    found_data = True

            # Check if any data was found at all
            if not found_data:
                self._update_status("status_compare_no_data_found")
                self._show_error("msg_title_compare_error", "msg_compare_no_data_found")
                return

            # Generate the comparison PDF
            self._update_status("status_compare_creating_pdf")
            # Use the function from compare.py
            pdf_path = generate_comparison_pdf(
                valid_tg_codes_for_header,
                all_car_data_formatted,
                DISPLAY_ORDER_WITH_DIVIDERS, # Use shared constant
                EXPORT_DIR_COMPARE # Use export dir from compare.py
            )

            if pdf_path:
                self._update_status("status_compare_success", path=pdf_path)
                self._show_info("msg_title_compare_success", "msg_compare_success", path=pdf_path)
            else:
                # If generate_comparison_pdf returns None without raising an exception
                self._update_status("status_compare_pdf_error")
                # Optionally show a generic error message
                self._show_error("msg_title_compare_error", "status_compare_pdf_error") # Re-use status key for message

        except sqlite3.Error as e:
            self._update_status("status_compare_db_error", error=e)
            self._show_error("msg_title_compare_error", "msg_compare_db_error", error=e)
        except OSError as e:
            self._update_status("status_compare_folder_error", error=e)
            self._show_error("msg_title_compare_error", "msg_compare_folder_error", path=EXPORT_DIR_COMPARE, error=e)
        except Exception as e:
            self._update_status("status_compare_error", error=e)
            self._show_error("msg_title_compare_error", "msg_compare_unknown_error", error=e)


# --- Main Execution ---
if __name__ == "__main__":
    # Basic check if DATABASE_PATH was imported correctly
    if 'DATABASE_PATH' not in globals():
         print("FATAL ERROR: DATABASE_PATH constant not found.")
         try:
             # Try to show an error popup even without full i18n setup yet
             root_err = tk.Tk(); root_err.withdraw()
             messagebox.showerror("Startup Error", "Fatal Error: DATABASE_PATH constant not defined.")
             root_err.destroy()
         except tk.TclError: pass # Ignore if Tkinter isn't available
         sys.exit(1)

    root = tk.Tk()
    app = VehicleDataApp(root) # Creates the UI, loads default language

    # Check for database existence *after* UI is created
    db_exists = os.path.exists(DATABASE_PATH)

    if not db_exists:
        print(f"Database '{DATABASE_PATH}' not found. Starting automatic import...")
        # Use translated prompt
        if messagebox.askyesno(_("msg_title_db_missing"), _("msg_db_missing_prompt", db_path=DATABASE_PATH)):
            # Run import in background thread, mark as startup import
            app._run_import_thread(is_startup=True)
        else:
             # User chose not to import, disable relevant UI elements
             messagebox.showinfo(_("msg_title_notice"), _("msg_db_missing_continue"))
             app.search_button.config(state=tk.DISABLED)
             app.export_button.config(state=tk.DISABLED)
             app.compare_button.config(state=tk.DISABLED)
             # Keep import enabled so they can try later
             # Assuming Import is always the first item in the Data menu (index 0)
             try:
                 app.data_menu.entryconfig(0, state=tk.NORMAL)
             except tk.TclError:
                 print("Warning: Could not ensure Import menu item is enabled at index 0.")

             app._update_status("status_db_missing_continue") # Update status bar
    else:
        # Database exists, enable UI elements
        print(f"Database '{DATABASE_PATH}' found. Starting application.")
        # Assuming Import is always the first item in the Data menu (index 0)
        try:
            app.data_menu.entryconfig(0, state=tk.NORMAL)
        except tk.TclError:
            print("Warning: Could not ensure Import menu item is enabled at index 0.")

        app.search_button.config(state=tk.NORMAL)
        # Export button state depends on whether data is loaded, initially disabled
        app.export_button.config(state=tk.DISABLED)
        app.compare_button.config(state=tk.NORMAL)
        app._update_status("status_ready") # Set initial status

    root.mainloop()
