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

# Import refactored components
import config
import database
import formatting
import importer
import export
import compare
import translation # Import the new translation module
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
        self.data_menu.add_command(label="TEMP_IMPORT", command=self._run_import_thread)
        # Use current_language from translation module after initialization
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
        self.compare_button = ttk.Button(self.compare_frame, text="TEMP_COMPARE_BTN", command=self._compare_vehicles)
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
        self.search_button = ttk.Button(search_button_frame, text="TEMP_SEARCH_BTN", command=self._search_vehicle)
        self.search_button.pack(side=tk.LEFT, padx=5)
        self.export_button = ttk.Button(search_button_frame, text="TEMP_EXPORT_BTN", command=self._export_vehicle_pdf)
        self.export_button.pack(side=tk.LEFT, padx=5)
        self.search_results_text = scrolledtext.ScrolledText(self.search_frame, height=25, width=80, wrap=tk.WORD, state=tk.DISABLED, font=("Courier New", 9))
        self.search_results_text.pack(side=tk.TOP, fill=tk.BOTH, expand=True, pady=(0,5))

        # --- Status Bar ---
        self.status_var = tk.StringVar()
        self.status_bar = ttk.Label(root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W, padding="2 5")
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        # --- Apply initial UI text ---
        self._update_ui_text() # Uses translation._ internally now

    # --- UI Update Methods ---
    def _build_menubar(self):
        """Deletes and rebuilds the main menubar cascades with current translations."""
        try: # Clear existing cascades first
            last_index = self.menubar.index(tk.END)
            if last_index is not None:
                for i in range(last_index, -1, -1): self.menubar.delete(i)
        except tk.TclError: pass # Ignore if menu is empty

        # Add cascades using translation._
        self.menubar.add_cascade(label=translation._("file_menu"), menu=self.file_menu)
        self.menubar.add_cascade(label=translation._("data_menu"), menu=self.data_menu)
        self.menubar.add_cascade(label=translation._("language_menu"), menu=self.language_menu)

    def _update_ui_text(self):
        """Updates static text elements in the UI based on current language."""
        # Use translation._ for all UI text
        self.root.title(translation._("window_title"))
        self._build_menubar() # Rebuild menu cascade labels

        # Update menu item labels
        try: self.file_menu.entryconfig(0, label=translation._("exit_menu"))
        except tk.TclError: print("Warning: Could not update 'Exit' menu item.")
        try: self.data_menu.entryconfig(0, label=translation._("import_menu"))
        except tk.TclError: print("Warning: Could not update 'Import' menu item.")

        # Update other widgets
        self.search_frame.config(text=translation._("search_export_frame"))
        self.compare_frame.config(text=translation._("compare_frame"))
        self.tg_code_search_label.config(text=translation._("tg_code_label"))
        self.compare_tg_codes_label.config(text=translation._("compare_tg_codes_label"))
        self.search_button.config(text=translation._("search_button"))
        self.export_button.config(text=translation._("export_pdf_button"))
        self.compare_button.config(text=translation._("compare_button"))

        # Update status bar only if it's showing a default message
        current_status = self.status_var.get()
        # Check against default message in *current* language
        is_default_status = (not current_status or current_status.startswith("[") or
                             current_status == translation._("status_ready"))
        if is_default_status: self.status_var.set(translation._("status_ready"))

        # Update waiting dialog if open
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

    def change_language(self, lang_code):
        """Sets the new language using the translation module and updates the UI."""
        # Use translation.set_language which handles loading
        if translation.set_language(lang_code):
            # Update the UI using the new translations (static elements)
            self._update_ui_text()
            # Update the radio button variable state
            self.selected_language_var.set(lang_code)

            # --- Re-run search if there's a TG-Code in the entry ---
            tg_code_in_entry = self.search_tg_code_entry.get().strip()
            if tg_code_in_entry:
                # Clear the current text area first for a cleaner update
                self.search_results_text.config(state=tk.NORMAL)
                self.search_results_text.delete('1.0', tk.END)
                self.search_results_text.config(state=tk.DISABLED)
                # Re-run the search logic - it will fetch data and format using the new language
                # This will update the search_results_text widget
                self._search_vehicle()
            # --- END Re-run search ---

        else:
            # Show error using the *current* language's translation
            messagebox.showerror(translation._("msg_title_import_error"), f"Could not load language: {lang_code}")
            # Optionally reset radio button to actual current language
            self.selected_language_var.set(translation.current_language)


    # --- Helper Methods (Messaging, Status) ---
    def _update_status(self, message_key, **kwargs):
        """Updates the status bar text (thread-safe)."""
        # Use translation._
        translated_message = translation._(message_key, **kwargs)
        self.root.after(0, self.status_var.set, translated_message)

    def _show_error(self, title_key, message_key, **kwargs):
        """Shows an error message box (thread-safe)."""
        # Use translation._
        title = translation._(title_key); message = translation._(message_key, **kwargs)
        self.root.after(0, messagebox.showerror, title, message)

    def _show_info(self, title_key, message_key, **kwargs):
        """Shows an info message box (thread-safe)."""
        # Use translation._
        title = translation._(title_key); message = translation._(message_key, **kwargs)
        self.root.after(0, messagebox.showinfo, title, message)

    # --- Waiting Dialog ---
    def _show_waiting_dialog(self):
        """Displays the modal progress dialog."""
        if self.waiting_dialog and self.waiting_dialog.winfo_exists(): return
        self.waiting_dialog = tk.Toplevel(self.root)
        # Use translation._
        self.waiting_dialog.title(translation._("waiting_dialog_title"))
        self.waiting_dialog.geometry("350x150"); self.waiting_dialog.resizable(False, False)
        self.waiting_dialog.transient(self.root); self.waiting_dialog.protocol("WM_DELETE_WINDOW", lambda: None)

        # Center dialog
        self.root.update_idletasks()
        root_x, root_y = self.root.winfo_rootx(), self.root.winfo_rooty()
        root_w, root_h = self.root.winfo_width(), self.root.winfo_height()
        dialog_w, dialog_h = 350, 150
        x = int(root_x + (root_w / 2) - (dialog_w / 2))
        y = int(root_y + (root_h / 2) - (dialog_h / 2))
        self.waiting_dialog.geometry(f"+{x}+{y}")

        dialog_frame = ttk.Frame(self.waiting_dialog, padding="10"); dialog_frame.pack(expand=True, fill=tk.BOTH)
        # Use translation._
        label_text = translation._("waiting_dialog_init") if self.import_running_at_startup else translation._("waiting_dialog_update")
        ttk.Label(dialog_frame, text=label_text, justify=tk.CENTER).pack(pady=(0, 10))
        self.progress_bar = ttk.Progressbar(dialog_frame, orient='horizontal', mode='determinate', variable=self.progress_var, maximum=100.0)
        self.progress_bar.pack(fill=tk.X, padx=10, pady=5)
        # Use translation._
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
            # Use translation._ (already corrected to pass float)
            progress_text = translation._("progress_percent", percentage=percentage)
            self.root.after(0, self.progress_var.set, percentage)
            self.root.after(0, self.progress_label_var.set, progress_text)
            if self.progress_bar and self.progress_bar.cget('mode') == 'indeterminate':
                 self.root.after(0, self.progress_bar.config, {'mode': 'determinate'})
        else: # Indeterminate progress
            # Use translation._
            progress_text = translation._("progress_ellipsis")
            self.root.after(0, self.progress_var.set, 0)
            self.root.after(0, self.progress_label_var.set, progress_text)
            if self.progress_bar and self.progress_bar.cget('mode') == 'determinate':
                 self.root.after(0, self.progress_bar.config, {'mode': 'indeterminate'})
                 self.root.after(0, self.progress_bar.start)


    # --- Core Application Logic ---

    # --- Import Handling ---
    def _run_import_thread(self, is_startup=False):
        """Starts the import process in a background thread."""
        self.import_running_at_startup = is_startup
        try: self.data_menu.entryconfig(0, state=tk.DISABLED)
        except tk.TclError: pass
        self.search_button.config(state=tk.DISABLED)
        self.export_button.config(state=tk.DISABLED)
        self.compare_button.config(state=tk.DISABLED)

        self._update_status("status_import_starting")
        self._show_waiting_dialog()
        self.progress_var.set(0.0)
        # Use translation._
        self.progress_label_var.set(translation._("progress_percent", percentage=0.0))
        if self.progress_bar: self.root.after(0, self.progress_bar.config, {'mode': 'determinate'})

        import_thread = threading.Thread(target=self._execute_import, daemon=True)
        import_thread.start()

    def _execute_import(self):
        """Target function for the import thread. Calls importer.main."""
        import_success = False
        try:
            self._update_status("status_import_running")
            importer.main(progress_callback=self._update_progress)
            if os.path.exists(config.DATABASE_PATH):
                 import_success = True
                 self._update_status("status_import_success")
                 if not self.import_running_at_startup:
                     self._show_info("msg_title_import_complete", "msg_import_complete")
            else:
                 raise FileNotFoundError(f"Database file '{config.DATABASE_PATH}' still not found after import.")

        except FileNotFoundError as e: self._update_status("status_import_error_file", error=e); self._show_error("msg_title_import_error", "msg_import_file_not_found", error=e)
        except sqlite3.Error as e: self._update_status("status_import_error_db", error=e); self._show_error("msg_title_import_error", "msg_import_db_error", error=e)
        except requests.exceptions.RequestException as e: self._update_status("status_import_error_download", error=e); self._show_error("msg_title_import_error", "msg_import_download_error", error=e)
        except IOError as e: self._update_status("status_import_error_io", error=e); self._show_error("msg_title_import_error", "msg_import_io_error", error=e)
        except OSError as e: self._update_status("status_import_error_os", error=e); self._show_error("msg_title_import_error", "msg_import_os_error", error=e)
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

        try: self.data_menu.entryconfig(0, state=tk.NORMAL)
        except tk.TclError: pass

        if db_now_exists:
            self._update_status("status_ready")
            self.search_button.config(state=tk.NORMAL)
            self.export_button.config(state=tk.NORMAL)
            self.compare_button.config(state=tk.NORMAL)
        else:
            self._update_status("status_db_missing_fail", db_path=config.DATABASE_PATH)
            self.search_button.config(state=tk.DISABLED)
            self.export_button.config(state=tk.DISABLED)
            self.compare_button.config(state=tk.DISABLED)
            if self.import_running_at_startup:
                self._show_error("msg_title_db_error", "msg_db_init_failed", db_path=config.DATABASE_PATH)

        self.import_running_at_startup = False

    # --- Search Handling ---
    def _search_vehicle(self):
        """Handles the search button click."""
        tg_code = self.search_tg_code_entry.get().strip()
        if not tg_code:
            # Only show error if triggered by button, not by language change
            # Check if the text area is currently empty (implies not a language change refresh)
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
                display_text = self._format_search_result_for_gui(formatted_data) # Uses translated labels
                self.search_results_text.insert(tk.END, display_text)
                self._update_status("status_search_found", code=tg_code)
            else:
                # Use translation._
                self.search_results_text.insert(tk.END, translation._("search_results_none", code=tg_code))
                self._update_status("status_search_not_found", code=tg_code)

        except sqlite3.Error as e:
            self._update_status("status_search_db_error", error=e)
            # Use translation._
            self.search_results_text.insert(tk.END, translation._("search_results_db_error", error=e))
            self._show_error("msg_title_search_error", "msg_search_db_error", error=e)
        except Exception as e:
            self._update_status("status_search_error", error=e)
            # Use translation._
            self.search_results_text.insert(tk.END, translation._("search_results_unknown_error", error=e))
            self._show_error("msg_title_search_error", "msg_search_unknown_error", error=e)
        finally:
            self.search_results_text.config(state=tk.DISABLED)

    def _format_search_result_for_gui(self, formatted_data):
        """Formats the already formatted data for display in the ScrolledText using translated labels."""
        lines = []
        # Use translation._
        lines.append(translation._("divider_text"))

        # --- Header ---
        tg_code_val = formatted_data.get('TG_Code', 'N/A')
        marke_val = formatted_data.get('Marke', 'N/A')
        typ_val = formatted_data.get('Typ', 'N/A')
        # Use translation._ for header format string
        lines.append(translation._("search_results_header", code=tg_code_val, make=marke_val, model=typ_val))
        lines.append(translation._("divider_text"))

        # --- Body ---
        for item_name in config.DISPLAY_ORDER_WITH_DIVIDERS:
            if item_name == config.DIVIDER_MARKER:
                lines.append(translation._("divider_text"))
                continue

            if item_name in ['TG_Code', 'Marke', 'Typ']:
                continue

            # Get the pre-formatted value (already translated if needed by formatting.py)
            display_value = formatted_data.get(item_name, "")
            # Get the translated label for the item_name
            translated_label = translation._(item_name)

            lines.append(f"{translated_label:<25}: {display_value}") # Use translated label

        lines.append(translation._("divider_text"))
        return "\n".join(lines)

    # --- Export Handling ---
    def _export_vehicle_pdf(self):
        """Handles the Export PDF button click."""
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

                    # export.py now handles internal formatting and translation via translation._
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

    # --- Compare Handling ---
    def _compare_vehicles(self):
        """Handles the Compare Vehicles button click."""
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
                # compare.py handles search, formatting, and value translation
                formatted_data = compare.get_formatted_car_data_for_compare(tg_code)
                all_formatted_data.append(formatted_data)
                valid_codes_found.append(tg_code)
                if formatted_data: found_data = True

            if not found_data:
                self._update_status("status_compare_no_data_found")
                self._show_error("msg_title_compare_error", "msg_compare_no_data_found")
                return

            self._update_status("status_compare_creating_pdf")
            # compare.py handles PDF label/header translation via translation._
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

    # --- File Opening Utility ---
    def _open_file(self, file_path):
        """Attempts to open the specified file using the default system application."""
        try:
            if sys.platform == "win32":
                os.startfile(file_path)
            elif sys.platform == "darwin": # macOS
                subprocess.call(['open', file_path])
            else: # Linux and other Unix-like systems
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
    app = VehicleDataApp(root) # Now uses translation._ for initial UI setup

    # Check for database existence at startup
    db_exists = os.path.exists(config.DATABASE_PATH)

    if not db_exists:
        print(f"Database '{config.DATABASE_PATH}' not found.")
        # Use translation._ for messagebox
        if messagebox.askyesno(translation._("msg_title_db_missing"), translation._("msg_db_missing_prompt", db_path=config.DATABASE_PATH)):
            app._run_import_thread(is_startup=True)
        else:
             messagebox.showinfo(translation._("msg_title_notice"), translation._("msg_db_missing_continue"))
             app.search_button.config(state=tk.DISABLED)
             app.export_button.config(state=tk.DISABLED)
             app.compare_button.config(state=tk.DISABLED)
             try: app.data_menu.entryconfig(0, state=tk.NORMAL)
             except tk.TclError: pass
             app._update_status("status_db_missing_continue")
    else:
        print(f"Database '{config.DATABASE_PATH}' found. Starting application.")
        try: app.data_menu.entryconfig(0, state=tk.NORMAL)
        except tk.TclError: pass
        app.search_button.config(state=tk.NORMAL)
        app.export_button.config(state=tk.NORMAL)
        app.compare_button.config(state=tk.NORMAL)
        app._update_status("status_ready")

    root.mainloop()
