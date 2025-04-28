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
from utils import get_resource_path

# --- Constants for Check Status ---
CHECK_UP_TO_DATE = 'UP_TO_DATE'
CHECK_UPDATE_AVAILABLE = 'UPDATE_AVAILABLE'
CHECK_DB_MISSING = 'DB_MISSING'
CHECK_TIMEOUT = 'TIMEOUT'
CHECK_ERROR = 'ERROR'

# --- Modified Check Function (No Download) ---
def check_for_updates(url, db_path):
    """
    Checks if a database update is available by comparing the DB modification time
    with the remote source file's time. Does NOT download.
    Returns a status string: CHECK_UP_TO_DATE, CHECK_UPDATE_AVAILABLE, CHECK_DB_MISSING, CHECK_TIMEOUT, CHECK_ERROR.
    """
    print("-" * 40)
    print(f"Checking for updates against database: {os.path.basename(db_path)}")
    db_mtime = None

    # 1. Check DB existence and modification time
    if not os.path.exists(db_path):
        print("Local database does not exist.")
        return CHECK_DB_MISSING # DB missing, import definitely needed

    try:
        db_timestamp = os.path.getmtime(db_path)
        db_mtime = datetime.fromtimestamp(db_timestamp, tz=timezone.utc).replace(tzinfo=None)
        print(f"Local database exists. Last modified (UTC): {db_mtime}")
    except Exception as e:
        print(f"Warning: Could not get modification time for database '{db_path}': {e}")
        # If we can't read DB time, assume update is needed to be safe
        return CHECK_UPDATE_AVAILABLE

    # 2. Check remote file modification time
    try:
        print("Checking remote source file modification date...")
        response = requests.head(url, timeout=config.STARTUP_CHECK_TIMEOUT)
        response.raise_for_status()

        if 'Last-Modified' in response.headers:
            remote_last_modified_str = response.headers['Last-Modified']
            remote_mtime_aware = parsedate_to_datetime(remote_last_modified_str)
            if remote_mtime_aware.tzinfo is not None:
                 remote_mtime = remote_mtime_aware.astimezone(timezone.utc).replace(tzinfo=None)
            else:
                 remote_mtime = remote_mtime_aware # Assume UTC
            print(f"Remote source file last modified (UTC): {remote_mtime}")

            if remote_mtime > db_mtime:
                print("Remote source file is newer than database.")
                return CHECK_UPDATE_AVAILABLE
            else:
                print("Local database is up-to-date with remote source.")
                return CHECK_UP_TO_DATE
        else:
            print("Warning: 'Last-Modified' header not found. Cannot determine if update is needed.")
            # Treat missing header as an error for the check phase
            return CHECK_ERROR

    except requests.exceptions.Timeout:
         print(f"Timeout occurred after {config.STARTUP_CHECK_TIMEOUT}s while checking remote file headers.")
         return CHECK_TIMEOUT
    except requests.exceptions.RequestException as e:
        print(f"Network error checking remote file headers: {e}.")
        return CHECK_ERROR
    except Exception as e:
        print(f"Error processing remote modification date: {e}.")
        # Treat processing error as check error
        return CHECK_ERROR
    finally:
        print("-" * 40)


# --- New Download Function ---
def download_source_file(url, download_target_path):
    """
    Downloads the source file from the URL to the target path.
    Returns True on success, False on failure.
    """
    print(f"Attempting to download source file to '{download_target_path}'...")
    try:
        download_dir = os.path.dirname(download_target_path)
        if not os.path.exists(download_dir):
            try:
                os.makedirs(download_dir)
                print(f"Created directory for download: {download_dir}")
            except OSError as e:
                print(f"Error creating directory '{download_dir}': {e}")
                return False # Cannot proceed without directory

        with requests.get(url, stream=True, timeout=config.DOWNLOAD_TIMEOUT) as r:
            r.raise_for_status()
            with open(download_target_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
        print("Download complete.")
        return True

    except requests.exceptions.Timeout:
         print(f"Timeout occurred during file download (limit: {config.DOWNLOAD_TIMEOUT}s).")
         return False
    except requests.exceptions.RequestException as e:
        print(f"Error downloading source file: {e}")
        return False
    except IOError as e:
        print(f"Error writing downloaded file '{download_target_path}': {e}")
        return False
    except Exception as e:
        print(f"An unexpected error occurred during download: {e}")
        return False
    finally:
        print("-" * 40)


# --- Modified Main Import Orchestration Function (Assumes File Exists) ---
def main(progress_callback=None):
    """
    Orchestrates the import process from the downloaded source file into the database.
    Assumes config.INPUT_FILE_PATH exists. Deletes the source file on success.
    """
    print("Starting database import process...") # Changed message
    conn = None
    import_successful = False

    # Check if source file exists before proceeding
    if not os.path.exists(config.INPUT_FILE_PATH):
         msg = f"Input file '{config.INPUT_FILE_PATH}' not found when starting main import function."
         print(f"ERROR: {msg}")
         raise FileNotFoundError(msg) # Raise error if file is missing

    try:
        print(f"Proceeding with import from '{config.INPUT_FILE_PATH}' to '{config.DATABASE_PATH}'...")

        # Count total rows
        total_rows = 0
        print("Counting total rows in input file...")
        try:
            with codecs.open(config.INPUT_FILE_PATH, 'r', encoding=config.FILE_ENCODING, errors='replace') as infile:
                reader = csv.reader(infile, delimiter=config.DELIMITER)
                header = next(reader)
                total_rows = sum(1 for row in reader)
            print(f"Found {total_rows} data rows.")
        except Exception as e:
            print(f"Warning: Could not accurately count rows: {e}.")
            total_rows = 0

        # Connect to DB
        conn = database.get_db_connection()
        cursor = conn.cursor()
        print("Database connection established.")

        # Create Schema
        header_map, normalized_table_mapping = database.create_schema(cursor)

        # Insert Data
        print("Starting data insertion...")
        with codecs.open(config.INPUT_FILE_PATH, 'r', encoding=config.FILE_ENCODING, errors='replace') as infile:
            reader = csv.reader(infile, delimiter=config.DELIMITER)
            next(reader)
            database.insert_data(conn, reader, header_map, normalized_table_mapping, total_rows, progress_callback)

        print("Import process finished successfully.")
        import_successful = True

    # Keep specific error handling for import phase
    except (sqlite3.Error, IOError, OSError) as import_err:
         print(f"An error occurred during the import process: {import_err}")
         if conn: conn.rollback()
         raise import_err
    except Exception as e:
         print(f"An unexpected error occurred during import: {e}")
         if conn: conn.rollback()
         raise e
    finally:
        if conn:
            conn.close()
            print("Database connection closed.")

        # Delete source file ONLY on successful import
        if import_successful:
            try:
                if os.path.exists(config.INPUT_FILE_PATH):
                    print(f"Attempting to delete source file: {config.INPUT_FILE_PATH}")
                    os.remove(config.INPUT_FILE_PATH)
                    print("Source file deleted successfully.")
                else:
                    print(f"Warning: Source file '{config.INPUT_FILE_PATH}' not found for deletion after successful import.")
            except OSError as e:
                print(f"Warning: Could not delete source file '{config.INPUT_FILE_PATH}' after successful import: {e}")
        else:
            if os.path.exists(config.INPUT_FILE_PATH):
                 print("Import did not complete successfully. Source file will NOT be deleted.")


# --- Main Execution Guard (for standalone running) ---
if __name__ == "__main__":
    try:
        # CLI run: Perform check, ask (implicitly yes for CLI), download, then import
        print("Running importer from command line...")
        check_result = check_for_updates(
            config.DOWNLOAD_URL,
            config.DATABASE_PATH
        )

        if check_result == CHECK_UPDATE_AVAILABLE or check_result == CHECK_DB_MISSING:
            print("Update required or database missing.")
            print("Attempting download...")
            download_ok = download_source_file(config.DOWNLOAD_URL, config.INPUT_FILE_PATH)
            if download_ok:
                print("Download successful. Proceeding with main import function...")
                main() # Run full import
            else:
                print("Download failed. Import cannot proceed.")
                sys.exit(1)
        elif check_result == CHECK_UP_TO_DATE:
            print("Database is up-to-date. No import performed.")
        else: # TIMEOUT or ERROR
            print(f"Update check failed with status: {check_result}. No import performed.")
            sys.exit(1)

    except Exception as e:
         print(f"\nImport process failed: {e}")
         sys.exit(1)
