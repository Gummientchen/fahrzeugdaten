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

# --- Download Function (Mostly unchanged, uses config) ---
def download_if_newer(url, local_path):
    """Downloads the file from the URL if it's newer than the local copy."""
    print("-" * 40)
    print(f"Checking file: {os.path.basename(local_path)}")
    print(f"URL: {url}")
    local_mtime = None
    download_needed = False

    # Ensure parent directory exists
    local_dir = os.path.dirname(local_path)
    if not os.path.exists(local_dir):
        try:
            os.makedirs(local_dir)
            print(f"Created directory: {local_dir}")
        except OSError as e:
            print(f"Error creating directory '{local_dir}': {e}")
            return False # Cannot proceed without directory

    # Check local file modification time
    if os.path.exists(local_path):
        try:
            local_timestamp = os.path.getmtime(local_path)
            # Convert to UTC naive datetime for comparison
            local_mtime = datetime.fromtimestamp(local_timestamp, tz=timezone.utc).replace(tzinfo=None)
            print(f"Local file exists. Last modified (UTC): {local_mtime}")
        except Exception as e:
            print(f"Warning: Could not get modification time for local file '{local_path}': {e}")
            download_needed = True # Download if unsure
    else:
        print("Local file does not exist.")
        download_needed = True

    # Check remote file modification time if local file exists and is readable
    if not download_needed and local_mtime:
        try:
            print("Checking remote file modification date...")
            response = requests.head(url, timeout=15) # Slightly longer timeout for HEAD
            response.raise_for_status() # Check for HTTP errors

            if 'Last-Modified' in response.headers:
                remote_last_modified_str = response.headers['Last-Modified']
                # Parse HTTP date string
                remote_mtime_aware = parsedate_to_datetime(remote_last_modified_str)
                # Convert to UTC naive datetime for comparison
                if remote_mtime_aware.tzinfo is not None:
                     remote_mtime = remote_mtime_aware.astimezone(timezone.utc).replace(tzinfo=None)
                else:
                     # Assume UTC if no timezone info (less common but possible)
                     remote_mtime = remote_mtime_aware
                print(f"Remote file last modified (UTC): {remote_mtime}")

                if remote_mtime > local_mtime:
                    print("Remote file is newer.")
                    download_needed = True
                else:
                    print("Local file is up-to-date.")
                    print("-" * 40)
                    return True # No download needed
            else:
                print("Warning: 'Last-Modified' header not found. Downloading file to ensure it's current.")
                download_needed = True

        except requests.exceptions.Timeout:
             print("Timeout occurred while checking remote file headers.")
             print("Proceeding with existing local file if present, otherwise download attempt.")
             if os.path.exists(local_path): return True
             else: download_needed = True # Need to download if local doesn't exist
        except requests.exceptions.RequestException as e:
            print(f"Error checking remote file headers: {e}")
            print("Proceeding with existing local file if present, otherwise download attempt.")
            if os.path.exists(local_path): return True
            else: download_needed = True # Need to download if local doesn't exist
        except Exception as e:
            # Catch potential errors during date parsing
            print(f"Error processing remote modification date: {e}")
            print("Downloading file to ensure it's current.")
            download_needed = True

    # Perform download if needed
    if download_needed:
        print(f"Downloading file to '{local_path}'...")
        try:
            # Use stream=True for potentially large files
            with requests.get(url, stream=True, timeout=120) as r: # Longer timeout for GET
                r.raise_for_status() # Check for HTTP errors during download
                with open(local_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
            print("Download complete.")
            print("-" * 40)
            return True # Download successful
        except requests.exceptions.Timeout:
             print("Timeout occurred during file download.")
             print("-" * 40)
             return False
        except requests.exceptions.RequestException as e:
            print(f"Error downloading file: {e}")
            print("-" * 40)
            return False
        except IOError as e:
            print(f"Error writing file '{local_path}': {e}")
            print("-" * 40)
            return False
        except Exception as e:
            print(f"An unexpected error occurred during download: {e}")
            print("-" * 40)
            return False

    # Should only reach here if local file was up-to-date initially
    print("-" * 40)
    return True


# --- Main Import Orchestration Function ---
def main(progress_callback=None):
    """Orchestrates the download and import process."""
    print("Starting import process...")

    # 1. Download data file if newer or missing
    if not download_if_newer(config.DOWNLOAD_URL, config.INPUT_FILE_PATH):
        # download_if_newer prints errors, raise specific exception for GUI
        raise requests.exceptions.RequestException("Download failed or file check error.")

    if not os.path.exists(config.INPUT_FILE_PATH):
         msg = f"Input file '{config.INPUT_FILE_PATH}' not found after download check."
         print(f"ERROR: {msg}")
         raise FileNotFoundError(msg)

    print(f"Proceeding with import from '{config.INPUT_FILE_PATH}' to '{config.DATABASE_PATH}'...")

    conn = None
    total_rows = 0
    try:
        # 2. Count total rows for progress reporting
        print("Counting total rows in input file...")
        try:
            with codecs.open(config.INPUT_FILE_PATH, 'r', encoding=config.FILE_ENCODING, errors='replace') as infile:
                reader = csv.reader(infile, delimiter=config.DELIMITER)
                header = next(reader) # Read header
                total_rows = sum(1 for row in reader) # Sum remaining lines
            print(f"Found {total_rows} data rows.")
        except Exception as e:
            print(f"Warning: Could not accurately count rows: {e}. Progress bar may be inaccurate or indeterminate.")
            total_rows = 0 # Reset if counting failed, progress will be indeterminate

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
            # Pass control to the database module for insertion
            database.insert_data(conn, reader, header_map, normalized_table_mapping, total_rows, progress_callback)

        print("Import process finished successfully.")

    except (sqlite3.Error, IOError, OSError, requests.exceptions.RequestException, FileNotFoundError) as e:
        print(f"An error occurred during the import process: {e}")
        if conn: conn.rollback()
        raise e # Re-raise the specific exception for GUI handling
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        if conn: conn.rollback()
        raise e # Re-raise generic exceptions
    finally:
        if conn:
            conn.close()
            print("Database connection closed.")

# --- Main Execution Guard (for standalone running) ---
if __name__ == "__main__":
    try:
        main() # Call without progress callback for CLI execution
    except Exception as e:
         print(f"\nImport process failed: {e}")
         sys.exit(1)
