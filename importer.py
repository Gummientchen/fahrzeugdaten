# importer.py
import os
import sqlite3
import sys
import requests
import codecs
import csv
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

# Import refactored components
import config
import database
from utils import get_resource_path # Might be needed if fonts were loaded here

# --- Renamed and Modified Check/Download Function ---
def check_import_needed_and_download(url, db_path, download_target_path):
    """
    Checks if a database import is needed by comparing the DB modification time
    with the remote source file's time. Downloads the source file if needed.
    Returns True if an import should proceed, False otherwise.
    """
    print("-" * 40)
    print(f"Checking database: {os.path.basename(db_path)}")
    db_mtime = None
    import_needed = False
    download_attempted = False

    # 1. Check DB modification time
    if os.path.exists(db_path):
        try:
            db_timestamp = os.path.getmtime(db_path)
            # Convert to UTC naive datetime for comparison
            db_mtime = datetime.fromtimestamp(db_timestamp, tz=timezone.utc).replace(tzinfo=None)
            print(f"Local database exists. Last modified (UTC): {db_mtime}")
        except Exception as e:
            print(f"Warning: Could not get modification time for database '{db_path}': {e}")
            import_needed = True # Import if unsure about DB age
    else:
        print("Local database does not exist.")
        import_needed = True # Import needed if DB doesn't exist

    # 2. Check remote file modification time if DB exists and we have its time
    if not import_needed and db_mtime:
        try:
            print("Checking remote source file modification date...")
            response = requests.head(url, timeout=15)
            response.raise_for_status()

            if 'Last-Modified' in response.headers:
                remote_last_modified_str = response.headers['Last-Modified']
                remote_mtime_aware = parsedate_to_datetime(remote_last_modified_str)
                # Convert to UTC naive datetime for comparison
                if remote_mtime_aware.tzinfo is not None:
                     remote_mtime = remote_mtime_aware.astimezone(timezone.utc).replace(tzinfo=None)
                else:
                     remote_mtime = remote_mtime_aware # Assume UTC
                print(f"Remote source file last modified (UTC): {remote_mtime}")

                if remote_mtime > db_mtime:
                    print("Remote source file is newer than database.")
                    import_needed = True
                else:
                    print("Local database is up-to-date with remote source.")
                    print("-" * 40)
                    return False # Import NOT needed
            else:
                print("Warning: 'Last-Modified' header not found. Assuming import is needed.")
                import_needed = True

        except requests.exceptions.Timeout:
             print("Timeout occurred while checking remote file headers. Assuming import is needed.")
             import_needed = True
        except requests.exceptions.RequestException as e:
            print(f"Error checking remote file headers: {e}. Assuming import is needed.")
            import_needed = True
        except Exception as e:
            print(f"Error processing remote modification date: {e}. Assuming import is needed.")
            import_needed = True

    # 3. Perform download ONLY if import is determined to be needed
    if import_needed:
        print(f"Import needed. Downloading source file to '{download_target_path}'...")
        download_attempted = True
        try:
            # Ensure parent directory exists for the download target
            download_dir = os.path.dirname(download_target_path)
            if not os.path.exists(download_dir):
                try:
                    os.makedirs(download_dir)
                    print(f"Created directory for download: {download_dir}")
                except OSError as e:
                    print(f"Error creating directory '{download_dir}': {e}")
                    raise # Re-raise directory creation error

            # Use stream=True for potentially large files
            with requests.get(url, stream=True, timeout=120) as r:
                r.raise_for_status() # Check for HTTP errors during download
                with open(download_target_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
            print("Download complete.")
            print("-" * 40)
            return True # Import IS needed because download was triggered and successful

        except requests.exceptions.RequestException as e:
            print(f"Error downloading source file: {e}")
            print("-" * 40)
            raise e # Re-raise download error to stop the process
        except IOError as e:
            print(f"Error writing downloaded file '{download_target_path}': {e}")
            print("-" * 40)
            raise e # Re-raise write error
        except Exception as e:
            print(f"An unexpected error occurred during download: {e}")
            print("-" * 40)
            raise e # Re-raise unexpected error

    # Should only reach here if DB existed and was up-to-date
    return False # Import NOT needed


# --- Main Import Orchestration Function ---
def main(progress_callback=None):
    """Orchestrates the download and import process."""
    print("Starting import process...")
    conn = None
    import_successful = False # Flag to track success for deletion

    try:
        # 1. Check if import is needed and download source if necessary
        import_is_required = check_import_needed_and_download(
            config.DOWNLOAD_URL,
            config.DATABASE_PATH,
            config.INPUT_FILE_PATH
        )

        if not import_is_required:
            print("Database is up-to-date. No import necessary.")
            return # Exit early if no import needed

        # --- Import is required, proceed ---

        # Check if source file exists after download attempt (should exist if import_is_required is True)
        if not os.path.exists(config.INPUT_FILE_PATH):
             msg = f"Input file '{config.INPUT_FILE_PATH}' not found even though import was required."
             print(f"ERROR: {msg}")
             raise FileNotFoundError(msg)

        print(f"Proceeding with import from '{config.INPUT_FILE_PATH}' to '{config.DATABASE_PATH}'...")

        # 2. Count total rows for progress reporting
        total_rows = 0
        print("Counting total rows in input file...")
        try:
            with codecs.open(config.INPUT_FILE_PATH, 'r', encoding=config.FILE_ENCODING, errors='replace') as infile:
                reader = csv.reader(infile, delimiter=config.DELIMITER)
                header = next(reader) # Read header
                total_rows = sum(1 for row in reader) # Sum remaining lines
            print(f"Found {total_rows} data rows.")
        except Exception as e:
            print(f"Warning: Could not accurately count rows: {e}. Progress bar may be inaccurate or indeterminate.")
            total_rows = 0 # Reset if counting failed

        # 3. Connect to Database
        conn = database.get_db_connection()
        cursor = conn.cursor()
        print("Database connection established.")

        # 4. Create Schema (will drop existing table)
        header_map, normalized_table_mapping = database.create_schema(cursor)

        # 5. Insert Data
        print("Starting data import...")
        with codecs.open(config.INPUT_FILE_PATH, 'r', encoding=config.FILE_ENCODING, errors='replace') as infile:
            reader = csv.reader(infile, delimiter=config.DELIMITER)
            next(reader) # Skip header row in the data file
            database.insert_data(conn, reader, header_map, normalized_table_mapping, total_rows, progress_callback)

        print("Import process finished successfully.")
        import_successful = True # Mark as successful for deletion step

    except (requests.exceptions.RequestException, FileNotFoundError) as pre_import_err:
         # Errors during check/download phase
         print(f"Pre-import check or download failed: {pre_import_err}")
         raise pre_import_err # Re-raise for GUI
    except (sqlite3.Error, IOError, OSError) as import_err:
         # Errors during the actual import (schema/insert)
         print(f"An error occurred during the import process: {import_err}")
         if conn: conn.rollback()
         # Do NOT delete source file if import failed
         raise import_err # Re-raise for GUI
    except Exception as e:
         print(f"An unexpected error occurred: {e}")
         if conn: conn.rollback()
         # Do NOT delete source file if import failed
         raise e # Re-raise generic exceptions
    finally:
        if conn:
            conn.close()
            print("Database connection closed.")

        # 6. Delete the source file ONLY AFTER successful import
        if import_successful:
            try:
                if os.path.exists(config.INPUT_FILE_PATH):
                    print(f"Attempting to delete source file: {config.INPUT_FILE_PATH}")
                    os.remove(config.INPUT_FILE_PATH)
                    print("Source file deleted successfully.")
                else:
                    # This might happen if the import was needed because DB didn't exist,
                    # but the source file was somehow already deleted. Benign warning.
                    print(f"Warning: Source file '{config.INPUT_FILE_PATH}' not found for deletion after successful import.")
            except OSError as e:
                print(f"Warning: Could not delete source file '{config.INPUT_FILE_PATH}' after successful import: {e}")
        else:
            if os.path.exists(config.INPUT_FILE_PATH):
                 print("Import did not complete successfully. Source file will NOT be deleted.")


# --- Main Execution Guard (for standalone running) ---
if __name__ == "__main__":
    try:
        main() # Call without progress callback for CLI execution
    except Exception as e:
         print(f"\nImport process failed: {e}")
         sys.exit(1)
