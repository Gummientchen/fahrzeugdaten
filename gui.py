# gui.py
import sqlite3
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, font
import threading
import os
import sys
import json
from datetime import datetime
import requests # Still needed for exception type hinting
import subprocess
import time # Import time for the simple dialog

# Import refactored components
import config
import database
import formatting
import importer # Import the module itself
import export
import compare
import translation
from utils import get_resource_path, clean_sql_identifier

# --- GUI Application Class ---
class VehicleDataApp:
    def __init__(self, root):
        self.root = root
        self.waiting_dialog = None
        self.import_running_at_startup = False
        self.progress_var = tk.DoubleVar()
        self.progress_bar = None
        self.progress_label_var = tk.StringVar()
        self.startup_check_dialog = None # For the initial check dialog
        self.update_check_result = None # To store result from check thread
        self.download_in_progress_dialog = None # For download message

        # --- Styling ---
        self.style = ttk.Style()
        self.style.theme_use('clam')
        default_font = font.nametofont("TkDefaultFont")
        default_font.configure(size=10)
        self.root.option_add("*Font", default_font)

        # --- Menu Bar ---
        self.menubar = tk.Menu(self.root)
        self.root.config(menu=self.menubar)

        # --- Create Menus ---
        self.file_menu = tk.Menu(self.menubar, tearoff=0)
        self.data_menu = tk.Menu(self.menubar, tearoff=0)
        self.language_menu = tk.Menu(self.menubar, tearoff=0)

        # --- Populate Menus ---
        self.file_menu.add_command(label="TEMP_EXIT", command=self.root.quit)
        # Disable import initially, enable after check if needed/possible
        self.data_menu.add_command(label="TEMP_IMPORT", command=self._trigger_manual_import, state=tk.DISABLED) # Changed command
        self.selected_language_var = tk.StringVar(value=translation.current_language)
        for code, name in config.SUPPORTED_LANGS.items():
             self.language_menu.add_radiobutton(
                 label=name, variable=self.selected_language_var, value=code,
                 command=lambda c=code: self.change_language(c)
             )

        # --- Main Frame ---
        main_frame = ttk.Frame(root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # --- Compare Section ---
        self.compare_frame = ttk.LabelFrame(main_frame, text="TEMP_COMPARE", padding="10")
        self.compare_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(5,0))
        compare_input_frame = ttk.Frame(self.compare_frame)
        compare_input_frame.pack(fill=tk.X)
        self.compare_tg_codes_label = ttk.Label(compare_input_frame, text="TEMP_COMPARE_LABEL")
        self.compare_tg_codes_label.pack(side=tk.LEFT, padx=5)
        self.compare_tg_codes_entry = ttk.Entry(compare_input_frame, width=40)
        self.compare_tg_codes_entry.pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)
        # Disable buttons initially
        self.compare_button = ttk.Button(self.compare_frame, text="TEMP_COMPARE_BTN", command=self._compare_vehicles, state=tk.DISABLED)
        self.compare_button.pack(pady=5)

        # --- Search/Export Section ---
        self.search_frame = ttk.LabelFrame(main_frame, text="TEMP_SEARCH", padding="10")
        self.search_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, pady=(0,5))
        search_input_frame = ttk.Frame(self.search_frame)
        search_input_frame.pack(side=tk.TOP, fill=tk.X)
        self.tg_code_search_label = ttk.Label(search_input_frame, text="TEMP_TG_CODE")
        self.tg_code_search_label.pack(side=tk.LEFT, padx=5)
        self.search_tg_code_entry = ttk.Entry(search_input_frame, width=20)
        self.search_tg_code_entry.pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)
        search_button_frame = ttk.Frame(self.search_frame)
        search_button_frame.pack(side=tk.TOP, fill=tk.X, pady=5)
        # Disable buttons initially
        self.search_button = ttk.Button(search_button_frame, text="TEMP_SEARCH_BTN", command=self._search_vehicle, state=tk.DISABLED)
        self.search_button.pack(side=tk.LEFT, padx=5)
        self.export_button = ttk.Button(search_button_frame, text="TEMP_EXPORT_BTN", command=self._export_vehicle_pdf, state=tk.DISABLED)
        self.export_button.pack(side=tk.LEFT, padx=5)
        self.search_results_text = scrolledtext.ScrolledText(self.search_frame, height=25, width=80, wrap=tk.WORD, state=tk.DISABLED, font=("Courier New", 9))
        self.search_results_text.pack(side=tk.TOP, fill=tk.BOTH, expand=True, pady=(0,5))

        # --- Status Bar ---
        self.status_var = tk.StringVar()
        self.status_bar = ttk.Label(root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W, padding="2 5")
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        # --- Apply initial UI text ---
        self._update_ui_text()

    # --- UI Update Methods ---
    def _build_menubar(self):
        """Deletes and rebuilds the main menubar cascades with current translations."""
        try:
            last_index = self.menubar.index(tk.END)
            if last_index is not None:
                for i in range(last_index, -1, -1): self.menubar.delete(i)
        except tk.TclError: pass

        self.menubar.add_cascade(label=translation._("file_menu"), menu=self.file_menu)
        self.menubar.add_cascade(label=translation._("data_menu"), menu=self.data_menu)
        self.menubar.add_cascade(label=translation._("language_menu"), menu=self.language_menu)

    def _update_ui_text(self):
        """Updates static text elements in the UI based on current language."""
        self.root.title(translation._("window_title"))
        self._build_menubar()

        try: self.file_menu.entryconfig(0, label=translation._("exit_menu"))
        except tk.TclError: print("Warning: Could not update 'Exit' menu item.")
        try: self.data_menu.entryconfig(0, label=translation._("import_menu"))
        except tk.TclError: print("Warning: Could not update 'Import' menu item.")

        self.search_frame.config(text=translation._("search_export_frame"))
        self.compare_frame.config(text=translation._("compare_frame"))
        self.tg_code_search_label.config(text=translation._("tg_code_label"))
        self.compare_tg_codes_label.config(text=translation._("compare_tg_codes_label"))
        self.search_button.config(text=translation._("search_button"))
        self.export_button.config(text=translation._("export_pdf_button"))
        self.compare_button.config(text=translation._("compare_button"))

        current_status = self.status_var.get()
        is_default_status = (not current_status or current_status.startswith("[") or
                             current_status == translation._("status_ready"))
        if is_default_status: self.status_var.set(translation._("status_ready"))

        if self.waiting_dialog and self.waiting_dialog.winfo_exists():
             self.waiting_dialog.title(translation._("waiting_dialog_title"))
             for widget in self.waiting_dialog.winfo_children():
                 if isinstance(widget, ttk.Frame):
                     for sub_widget in widget.winfo_children():
                         if isinstance(sub_widget, ttk.Label) and "%" not in sub_widget.cget("text") and "..." not in sub_widget.cget("text"):
                             label_text = translation._("waiting_dialog_init") if self.import_running_at_startup else translation._("waiting_dialog_update")
                             sub_widget.config(text=label_text)
                             break
                     break
        if self.startup_check_dialog and self.startup_check_dialog.winfo_exists():
            self.startup_check_dialog.title(translation._("startup_check_title"))
            for widget in self.startup_check_dialog.winfo_children():
                if isinstance(widget, ttk.Label):
                    widget.config(text=translation._("startup_check_message"))
                    break
        # Update download dialog if it exists
        if self.download_in_progress_dialog and self.download_in_progress_dialog.winfo_exists():
            self.download_in_progress_dialog.title(translation._("download_dialog_title"))
            for widget in self.download_in_progress_dialog.winfo_children():
                if isinstance(widget, ttk.Label):
                    widget.config(text=translation._("download_dialog_message"))
                    break


    def change_language(self, lang_code):
        """Sets the new language using the translation module and updates the UI."""
        if translation.set_language(lang_code):
            self._update_ui_text()
            self.selected_language_var.set(lang_code)
            tg_code_in_entry = self.search_tg_code_entry.get().strip()
            if tg_code_in_entry:
                self.search_results_text.config(state=tk.NORMAL)
                self.search_results_text.delete('1.0', tk.END)
                self.search_results_text.config(state=tk.DISABLED)
                self._search_vehicle()
        else:
            messagebox.showerror(translation._("msg_title_import_error"), f"Could not load language: {lang_code}")
            self.selected_language_var.set(translation.current_language)

    # --- Helper Methods (Messaging, Status) ---
    def _update_status(self, message_key, **kwargs):
        translated_message = translation._(message_key, **kwargs)
        self.root.after(0, self.status_var.set, translated_message)

    def _show_error(self, title_key, message_key, **kwargs):
        title = translation._(title_key); message = translation._(message_key, **kwargs)
        self.root.after(0, messagebox.showerror, title, message)

    def _show_info(self, title_key, message_key, **kwargs):
        title = translation._(title_key); message = translation._(message_key, **kwargs)
        self.root.after(0, messagebox.showinfo, title, message)

    # --- Waiting Dialog (Full Import) ---
    def _show_waiting_dialog(self):
        """Displays the modal progress dialog for the full import."""
        if self.waiting_dialog and self.waiting_dialog.winfo_exists(): return
        self.waiting_dialog = tk.Toplevel(self.root)
        self.waiting_dialog.title(translation._("waiting_dialog_title"))
        self.waiting_dialog.geometry("350x150"); self.waiting_dialog.resizable(False, False)
        self.waiting_dialog.transient(self.root); self.waiting_dialog.protocol("WM_DELETE_WINDOW", lambda: None)
        self.root.update_idletasks()
        root_x, root_y = self.root.winfo_rootx(), self.root.winfo_rooty()
        root_w, root_h = self.root.winfo_width(), self.root.winfo_height()
        dialog_w, dialog_h = 350, 150
        x = int(root_x + (root_w / 2) - (dialog_w / 2))
        y = int(root_y + (root_h / 2) - (dialog_h / 2))
        self.waiting_dialog.geometry(f"+{x}+{y}")
        dialog_frame = ttk.Frame(self.waiting_dialog, padding="10"); dialog_frame.pack(expand=True, fill=tk.BOTH)
        label_text = translation._("waiting_dialog_init") if self.import_running_at_startup else translation._("waiting_dialog_update")
        ttk.Label(dialog_frame, text=label_text, justify=tk.CENTER).pack(pady=(0, 10))
        self.progress_bar = ttk.Progressbar(dialog_frame, orient='horizontal', mode='determinate', variable=self.progress_var, maximum=100.0)
        self.progress_bar.pack(fill=tk.X, padx=10, pady=5)
        initial_progress_text = translation._("progress_percent", percentage=0.0); self.progress_label_var.set(initial_progress_text)
        ttk.Label(dialog_frame, textvariable=self.progress_label_var).pack(pady=(0, 5))
        self.progress_var.set(0.0)
        self.waiting_dialog.grab_set(); self.root.update_idletasks()

    def _close_waiting_dialog(self):
        """Closes the modal progress dialog."""
        if self.waiting_dialog and self.waiting_dialog.winfo_exists():
            self.waiting_dialog.grab_release(); self.waiting_dialog.destroy()
            self.waiting_dialog = None; self.progress_bar = None

    def _update_progress(self, current_row, total_rows):
        """Callback function to update the progress bar (thread-safe)."""
        if total_rows > 0:
            percentage = min((current_row / total_rows) * 100.0, 100.0)
            progress_text = translation._("progress_percent", percentage=percentage)
            self.root.after(0, self.progress_var.set, percentage)
            self.root.after(0, self.progress_label_var.set, progress_text)
            if self.progress_bar and self.progress_bar.cget('mode') == 'indeterminate':
                 self.root.after(0, self.progress_bar.config, {'mode': 'determinate'})
        else:
            progress_text = translation._("progress_ellipsis")
            self.root.after(0, self.progress_var.set, 0)
            self.root.after(0, self.progress_label_var.set, progress_text)
            if self.progress_bar and self.progress_bar.cget('mode') == 'determinate':
                 self.root.after(0, self.progress_bar.config, {'mode': 'indeterminate'})
                 self.root.after(0, self.progress_bar.start)

    # --- Startup Update Check ---
    def _show_startup_check_dialog(self):
        """Displays a simple non-modal dialog while checking for updates."""
        if self.startup_check_dialog and self.startup_check_dialog.winfo_exists():
            return
        self.startup_check_dialog = tk.Toplevel(self.root)
        self.startup_check_dialog.title(translation._("startup_check_title"))
        self.startup_check_dialog.geometry("300x100")
        self.startup_check_dialog.resizable(False, False)
        self.startup_check_dialog.transient(self.root)
        self.startup_check_dialog.protocol("WM_DELETE_WINDOW", lambda: None)
        self.root.update_idletasks()
        root_x, root_y = self.root.winfo_rootx(), self.root.winfo_rooty()
        root_w, root_h = self.root.winfo_width(), self.root.winfo_height()
        dialog_w, dialog_h = 300, 100
        x = int(root_x + (root_w / 2) - (dialog_w / 2))
        y = int(root_y + (root_h / 2) - (dialog_h / 2))
        self.startup_check_dialog.geometry(f"+{x}+{y}")
        label = ttk.Label(self.startup_check_dialog, text=translation._("startup_check_message"), padding="10 10 10 10", justify=tk.CENTER)
        label.pack(expand=True, fill=tk.BOTH)
        self.root.update_idletasks()

    def _close_startup_check_dialog(self):
        """Closes the startup check dialog."""
        if self.startup_check_dialog and self.startup_check_dialog.winfo_exists():
            self.startup_check_dialog.destroy()
            self.startup_check_dialog = None

    def _perform_startup_update_check(self):
        """Initiates the update check in a background thread."""
        print("Performing startup update check...")
        self._show_startup_check_dialog()
        self.update_check_result = None
        check_thread = threading.Thread(target=self._execute_update_check, daemon=True)
        check_thread.start()

    def _execute_update_check(self):
        """Target function for the update check thread."""
        try:
            # Call the modified check function (no download)
            result = importer.check_for_updates(
                config.DOWNLOAD_URL,
                config.DATABASE_PATH
            )
            self.update_check_result = result
        except Exception as e:
            print(f"ERROR during startup check execution: {e}")
            self.update_check_result = importer.CHECK_ERROR
        finally:
            self.root.after(0, self._handle_update_check_result)

    def _handle_update_check_result(self):
        """Processes the result of the startup update check (runs in main thread)."""
        self._close_startup_check_dialog()
        result = self.update_check_result
        print(f"Startup check result: {result}")

        user_wants_update = False
        user_declined_update = False

        if result == importer.CHECK_UPDATE_AVAILABLE:
            if messagebox.askyesno(
                translation._("msg_title_update_available"),
                translation._("msg_update_available_prompt") # Use generic prompt
            ):
                user_wants_update = True
            else:
                user_declined_update = True
        elif result == importer.CHECK_DB_MISSING:
             if messagebox.askyesno(
                translation._("msg_title_db_missing"), # Use DB missing title
                translation._("msg_db_missing_prompt", db_path=config.DATABASE_PATH) # Use DB missing prompt
            ):
                user_wants_update = True # Treat as wanting update/initial import
             else:
                 user_declined_update = True # User declined initial import
        elif result == importer.CHECK_TIMEOUT:
            messagebox.showwarning(
                translation._("msg_title_update_check_failed"),
                translation._("msg_update_check_timeout", timeout=config.STARTUP_CHECK_TIMEOUT)
            )
        elif result == importer.CHECK_ERROR:
            messagebox.showerror(
                translation._("msg_title_update_check_failed"),
                translation._("msg_update_check_error")
            )
        elif result == importer.CHECK_UP_TO_DATE:
            self._update_status("status_db_up_to_date")
        else:
             print(f"Warning: Unknown update check result '{result}'")

        # --- Enable UI or Trigger Download ---
        db_exists_now = os.path.exists(config.DATABASE_PATH)

        # Always enable Import menu item after check
        try: self.data_menu.entryconfig(0, state=tk.NORMAL)
        except tk.TclError: pass

        if user_wants_update:
            # Trigger the download process
            self._run_download_thread(is_startup=True) # Pass startup flag
        else:
            # Enable UI based on current DB state if user declined or check failed/up-to-date
            if db_exists_now:
                self.search_button.config(state=tk.NORMAL)
                self.export_button.config(state=tk.NORMAL)
                self.compare_button.config(state=tk.NORMAL)
                if user_declined_update and result == importer.CHECK_UPDATE_AVAILABLE:
                    self._update_status("status_update_declined")
                elif user_declined_update and result == importer.CHECK_DB_MISSING:
                     self._update_status("status_db_missing_continue")
                elif result != importer.CHECK_UP_TO_DATE: # Timeout or Error, but DB exists
                     self._update_status("status_ready") # Set to ready
            else: # No DB and user declined initial import or check failed
                self.search_button.config(state=tk.DISABLED)
                self.export_button.config(state=tk.DISABLED)
                self.compare_button.config(state=tk.DISABLED)
                if user_declined_update:
                     self._update_status("status_db_missing_continue")
                # If check failed and no DB, status bar might show error already

    # --- Download Phase ---
    def _show_download_dialog(self):
        """Shows a simple dialog indicating download is in progress."""
        if self.download_in_progress_dialog and self.download_in_progress_dialog.winfo_exists():
            return
        self.download_in_progress_dialog = tk.Toplevel(self.root)
        self.download_in_progress_dialog.title(translation._("download_dialog_title"))
        self.download_in_progress_dialog.geometry("300x100")
        self.download_in_progress_dialog.resizable(False, False)
        self.download_in_progress_dialog.transient(self.root)
        self.download_in_progress_dialog.protocol("WM_DELETE_WINDOW", lambda: None) # Prevent closing
        self.root.update_idletasks()
        root_x, root_y = self.root.winfo_rootx(), self.root.winfo_rooty()
        root_w, root_h = self.root.winfo_width(), self.root.winfo_height()
        dialog_w, dialog_h = 300, 100
        x = int(root_x + (root_w / 2) - (dialog_w / 2))
        y = int(root_y + (root_h / 2) - (dialog_h / 2))
        self.download_in_progress_dialog.geometry(f"+{x}+{y}")
        label = ttk.Label(self.download_in_progress_dialog, text=translation._("download_dialog_message"), padding="10 10 10 10", justify=tk.CENTER)
        label.pack(expand=True, fill=tk.BOTH)
        self.download_in_progress_dialog.grab_set() # Make it modal during download
        self.root.update_idletasks()

    def _close_download_dialog(self):
        """Closes the download dialog."""
        if self.download_in_progress_dialog and self.download_in_progress_dialog.winfo_exists():
            self.download_in_progress_dialog.grab_release()
            self.download_in_progress_dialog.destroy()
            self.download_in_progress_dialog = None

    def _run_download_thread(self, is_startup=False):
        """Starts the download process in a background thread."""
        print("Starting download thread...")
        self._show_download_dialog()
        # Disable import menu while downloading
        try: self.data_menu.entryconfig(0, state=tk.DISABLED)
        except tk.TclError: pass
        self._update_status("status_downloading") # New status

        download_thread = threading.Thread(
            target=self._execute_download,
            args=(is_startup,), # Pass startup flag if needed later
            daemon=True
        )
        download_thread.start()

    def _execute_download(self, is_startup):
        """Target function for the download thread."""
        download_ok = False
        try:
            download_ok = importer.download_source_file(
                config.DOWNLOAD_URL,
                config.INPUT_FILE_PATH
            )
        except Exception as e:
            print(f"ERROR during download execution: {e}")
            download_ok = False # Ensure it's false on exception
        finally:
            # Schedule result handler on main thread
            self.root.after(0, self._handle_download_result, download_ok, is_startup)

    def _handle_download_result(self, download_successful, is_startup):
        """Handles the result of the download attempt."""
        self._close_download_dialog()
        # Re-enable import menu item
        try: self.data_menu.entryconfig(0, state=tk.NORMAL)
        except tk.TclError: pass

        if download_successful:
            print("Download successful, proceeding to import.")
            # Now trigger the actual import process
            self._run_import_thread(is_startup=is_startup)
        else:
            print("Download failed.")
            self._update_status("status_download_failed") # New status
            self._show_error("msg_title_download_error", "msg_download_failed") # New message
            # Enable UI based on whether DB exists *now* (it might exist from previous run)
            db_exists_now = os.path.exists(config.DATABASE_PATH)
            if db_exists_now:
                self.search_button.config(state=tk.NORMAL)
                self.export_button.config(state=tk.NORMAL)
                self.compare_button.config(state=tk.NORMAL)
                self._update_status("status_ready") # Ready, but download failed
            else:
                self.search_button.config(state=tk.DISABLED)
                self.export_button.config(state=tk.DISABLED)
                self.compare_button.config(state=tk.DISABLED)
                self._update_status("status_db_missing_continue") # Still missing


    # --- Import Handling ---
    def _trigger_manual_import(self):
        """Handles the 'Import/Update Data' menu click."""
        # Ask the user if they are sure, as it involves download and overwrite
        if messagebox.askyesno(
            translation._("msg_title_manual_import"),
            translation._("msg_manual_import_prompt")
        ):
            # If yes, start the download process, which will trigger import on success
            self._run_download_thread(is_startup=False) # Not a startup import

    def _run_import_thread(self, is_startup=False):
        """Starts the import process in a background thread. Assumes download is complete."""
        self.import_running_at_startup = is_startup
        # Disable import menu again during actual import
        try: self.data_menu.entryconfig(0, state=tk.DISABLED)
        except tk.TclError: pass
        self.search_button.config(state=tk.DISABLED)
        self.export_button.config(state=tk.DISABLED)
        self.compare_button.config(state=tk.DISABLED)

        self._update_status("status_import_starting")
        self._show_waiting_dialog() # Show the full progress dialog
        self.progress_var.set(0.0)
        self.progress_label_var.set(translation._("progress_percent", percentage=0.0))
        if self.progress_bar: self.root.after(0, self.progress_bar.config, {'mode': 'determinate'})

        import_thread = threading.Thread(target=self._execute_import, daemon=True)
        import_thread.start()

    def _execute_import(self):
        """Target function for the import thread. Calls importer.main."""
        import_success = False
        try:
            self._update_status("status_import_running")
            # Call importer.main which now assumes download happened
            importer.main(progress_callback=self._update_progress)
            if os.path.exists(config.DATABASE_PATH):
                 import_success = True
                 self._update_status("status_import_success")
                 if not self.import_running_at_startup:
                     self._show_info("msg_title_import_complete", "msg_import_complete")
                 else:
                      print("Startup import completed successfully.")
            else:
                 raise FileNotFoundError(f"Database file '{config.DATABASE_PATH}' still not found after import.")
        except (FileNotFoundError, sqlite3.Error, IOError, OSError) as e:
             # Handle errors during the import itself
             self._update_status("status_import_error_db", error=e)
             self._show_error("msg_title_import_error", "msg_import_db_error", error=e)
        except Exception as e:
            self._update_status("status_import_error_unknown", error=e); self._show_error("msg_title_import_error", "msg_import_unknown_error", error=e)
            import traceback
            traceback.print_exc()
        finally:
            self.root.after(0, self._finalize_import, import_success)

    def _finalize_import(self, import_successful):
        """Updates UI after import attempt completes (runs in main thread)."""
        self._close_waiting_dialog()
        db_now_exists = os.path.exists(config.DATABASE_PATH)
        self.progress_var.set(0.0); self.progress_label_var.set("")

        # Re-enable Import menu item
        try: self.data_menu.entryconfig(0, state=tk.NORMAL)
        except tk.TclError: pass

        if db_now_exists:
            if not import_successful:
                 self._update_status("status_ready") # Or keep error status? Let's use ready.
            self.search_button.config(state=tk.NORMAL)
            self.export_button.config(state=tk.NORMAL)
            self.compare_button.config(state=tk.NORMAL)
        else:
            self._update_status("status_db_missing_fail", db_path=config.DATABASE_PATH)
            self.search_button.config(state=tk.DISABLED)
            self.export_button.config(state=tk.DISABLED)
            self.compare_button.config(state=tk.DISABLED)
            # Don't show error again if it was startup, already handled potentially
            # if self.import_running_at_startup:
            #     self._show_error("msg_title_db_error", "msg_db_init_failed", db_path=config.DATABASE_PATH)

        self.import_running_at_startup = False

    # --- Search, Format, Export, Compare, Open File ---
    # (No changes needed in these methods)
    def _search_vehicle(self):
        tg_code = self.search_tg_code_entry.get().strip()
        if not tg_code:
            if not self.search_results_text.get('1.0', 'end-1c'):
                 self._show_error("msg_title_input_missing", "msg_input_tg_code_search")
            return
        self._update_status("status_searching", code=tg_code)
        self.search_results_text.config(state=tk.NORMAL)
        self.search_results_text.delete('1.0', tk.END)
        try:
            raw_data_row = database.search_by_tg_code(tg_code)
            if raw_data_row:
                formatted_data = formatting.format_vehicle_data(raw_data_row)
                display_text = self._format_search_result_for_gui(formatted_data)
                self.search_results_text.insert(tk.END, display_text)
                self._update_status("status_search_found", code=tg_code)
            else:
                self.search_results_text.insert(tk.END, translation._("search_results_none", code=tg_code))
                self._update_status("status_search_not_found", code=tg_code)
        except sqlite3.Error as e:
            self._update_status("status_search_db_error", error=e)
            self.search_results_text.insert(tk.END, translation._("search_results_db_error", error=e))
            self._show_error("msg_title_search_error", "msg_search_db_error", error=e)
        except Exception as e:
            self._update_status("status_search_error", error=e)
            self.search_results_text.insert(tk.END, translation._("search_results_unknown_error", error=e))
            self._show_error("msg_title_search_error", "msg_search_unknown_error", error=e)
        finally:
            self.search_results_text.config(state=tk.DISABLED)

    def _format_search_result_for_gui(self, formatted_data):
        lines = []
        lines.append(translation._("divider_text"))
        tg_code_val = formatted_data.get('TG_Code', 'N/A')
        marke_val = formatted_data.get('Marke', 'N/A')
        typ_val = formatted_data.get('Typ', 'N/A')
        lines.append(translation._("search_results_header", code=tg_code_val, make=marke_val, model=typ_val))
        lines.append(translation._("divider_text"))
        for item_name in config.DISPLAY_ORDER_WITH_DIVIDERS:
            if item_name == config.DIVIDER_MARKER:
                lines.append(translation._("divider_text"))
                continue
            if item_name in ['TG_Code', 'Marke', 'Typ']:
                continue
            display_value = formatted_data.get(item_name, "")
            translated_label = translation._(item_name)
            lines.append(f"{translated_label:<25}: {display_value}")
        lines.append(translation._("divider_text"))
        return "\n".join(lines)

    def _export_vehicle_pdf(self):
        tg_code = self.search_tg_code_entry.get().strip()
        if not tg_code:
            self._show_error("msg_title_input_missing", "msg_input_tg_code_export")
            return
        self._update_status("status_searching", code=tg_code)
        try:
            raw_data_row = database.search_by_tg_code(tg_code)
            if raw_data_row:
                self._update_status("status_exporting", code=tg_code)
                try:
                    os.makedirs(config.EXPORT_DIR_SINGLE, exist_ok=True)
                    cleaned_name_part = clean_sql_identifier(tg_code)
                    safe_filename_part = cleaned_name_part.lstrip('_')
                    base_filename = f"{safe_filename_part}.pdf"
                    full_pdf_path = os.path.join(config.EXPORT_DIR_SINGLE, base_filename)
                    success = export.create_single_pdf(raw_data_row, full_pdf_path)
                    if success:
                        self._update_status("status_export_success", path=full_pdf_path)
                        self._open_file(full_pdf_path)
                    else:
                        self._update_status("status_export_error_unknown", error="PDF generation failed")
                        self._show_error("msg_title_export_error", "msg_export_unknown_error", error="PDF generation failed")
                except OSError as e:
                    self._update_status("status_export_folder_error", error=e)
                    self._show_error("msg_title_export_error", "msg_export_folder_error", path=config.EXPORT_DIR_SINGLE, error=e)
                except Exception as e:
                    self._update_status("status_export_error", error=e)
                    self._show_error("msg_title_export_error", "msg_export_unknown_error", error=e)
            else:
                self._update_status("status_search_not_found", code=tg_code)
                self._show_error("msg_title_search_error", "msg_search_not_found", code=tg_code)
        except sqlite3.Error as e:
            self._update_status("status_search_db_error", error=e)
            self._show_error("msg_title_search_error", "msg_search_db_error", error=e)
        except Exception as e:
            self._update_status("status_search_error", error=e)
            self._show_error("msg_title_search_error", "msg_search_unknown_error", error=e)

    def _compare_vehicles(self):
        tg_codes_str = self.compare_tg_codes_entry.get().strip()
        if not tg_codes_str:
            self._show_error("msg_title_input_missing", "msg_input_tg_code_compare")
            return
        tg_codes_input = [code.strip() for code in tg_codes_str.split(',') if code.strip()]
        if not (2 <= len(tg_codes_input) <= 3):
            self._show_error("msg_title_compare_error", "msg_compare_invalid_input")
            return
        codes_str = ', '.join(tg_codes_input)
        self._update_status("status_comparing", codes=codes_str)
        all_formatted_data = []
        valid_codes_found = []
        found_data = False
        try:
            for tg_code in tg_codes_input:
                self._update_status("status_compare_fetching", code=tg_code)
                formatted_data = compare.get_formatted_car_data_for_compare(tg_code)
                all_formatted_data.append(formatted_data)
                valid_codes_found.append(tg_code)
                if formatted_data: found_data = True
            if not found_data:
                self._update_status("status_compare_no_data_found")
                self._show_error("msg_title_compare_error", "msg_compare_no_data_found")
                return
            self._update_status("status_compare_creating_pdf")
            pdf_path = compare.generate_comparison_pdf(valid_codes_found, all_formatted_data)
            if pdf_path:
                self._update_status("status_compare_success", path=pdf_path)
                self._open_file(pdf_path)
            else:
                self._update_status("status_compare_pdf_error")
                self._show_error("msg_title_compare_error", "status_compare_pdf_error")
        except sqlite3.Error as e:
            self._update_status("status_compare_db_error", error=e)
            self._show_error("msg_title_compare_error", "msg_compare_db_error", error=e)
        except OSError as e:
            self._update_status("status_compare_folder_error", error=e)
            self._show_error("msg_title_compare_error", "msg_compare_folder_error", path=config.EXPORT_DIR_COMPARE, error=e)
        except Exception as e:
            self._update_status("status_compare_error", error=e)
            self._show_error("msg_title_compare_error", "msg_compare_unknown_error", error=e)

    def _open_file(self, file_path):
        try:
            if sys.platform == "win32":
                os.startfile(file_path)
            elif sys.platform == "darwin":
                subprocess.call(['open', file_path])
            else:
                subprocess.call(['xdg-open', file_path])
            print(f"Attempted to open file: {file_path}")
        except FileNotFoundError:
            msg = f"Could not find default application opener for platform '{sys.platform}'. Please open the file manually."
            print(f"Warning: {msg}\nPath: '{file_path}'")
        except Exception as e:
            print(f"Error attempting to open file '{file_path}': {e}")


# --- Main Execution ---
if __name__ == "__main__":
    # Initialize translations FIRST
    translation.initialize_translations()

    root = tk.Tk()
    app = VehicleDataApp(root) # Creates UI, initially disabled

    # Perform startup check *before* starting the main loop
    app._perform_startup_update_check()

    # Start the Tkinter main loop
    root.mainloop()
