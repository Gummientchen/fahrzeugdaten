# import.py
import sqlite3
import csv
import os
import codecs
import re
import requests # For downloading
from datetime import datetime, timezone # For date comparison
from email.utils import parsedate_to_datetime # For parsing HTTP dates

# --- Configuration ---
# *** NEW: Download URL ***
DOWNLOAD_URL = "https://opendata.astra.admin.ch/ivzod/2000-Typengenehmigungen_TG_TARGA/2200-Basisdaten_TG_ab_1995/emissionen.txt"
DATA_DIR = "data" # Define data directory name
INPUT_FILENAME = "emissionen.txt"
INPUT_FILE_PATH = os.path.join(DATA_DIR, INPUT_FILENAME) # Use defined constants
DATABASE_PATH = 'emissionen.db'
FILE_ENCODING = 'windows-1252' # Or 'cp1252'
DB_ENCODING = 'utf-8'
DELIMITER = '\t' # Assuming tab-separated, adjust if needed

# Columns to normalize (unique values stored in separate tables)
NORMALIZE_COLUMNS = [
    "Marke",
    "Getriebe",
    "Motormarke",
    "Motortyp",
    "Treibstoff",
    "Abgasreinigung",
    "Antrieb",
    "Anzahl_Achsen_Räder", # Note: Might contain non-unique descriptions like '2/4', consider if truly needs normalization
    "AbgasCode",
    "Emissionscode",
    "GeräuschCode"
]

# --- Helper Functions ---

def clean_sql_identifier(name):
    """Cleans a string to be a valid SQL identifier (table/column name)."""
    if not isinstance(name, str): return "" # Handle non-string input
    # Replace problematic characters with underscores
    name = re.sub(r'[ /.\-+()]+', '_', name)
    # Remove trailing underscores
    name = name.strip('_')
    # Ensure it doesn't start with a number (though unlikely with these headers)
    if name and name[0].isdigit(): # Check name is not empty
        name = '_' + name
    return name

def create_normalized_table_name(base_name):
    """Creates a pluralized table name for normalized columns."""
    # Simple pluralization, might need adjustment for edge cases
    clean_name = clean_sql_identifier(base_name)
    if not clean_name: return None # Handle empty base_name
    if clean_name.endswith('e'):
         # Avoid Marke -> Markee, Getriebe -> Getriebee
         return f"{clean_name}n"
    elif clean_name.endswith('s'):
        return f"{clean_name}es"
    else:
        return f"{clean_name}s"

def get_or_insert_normalized_id(cursor, table_name, value, cache):
    """
    Gets the ID for a value in a normalized table.
    Inserts the value if it doesn't exist.
    Uses a cache for performance.
    """
    if value is None or value == '':
        value = '(leer)' # Represent empty strings explicitly

    cache_key = (table_name, value)
    if cache_key in cache:
        return cache[cache_key]

    # Check if value exists
    select_sql = f"SELECT id FROM {table_name} WHERE name = ?"
    cursor.execute(select_sql, (value,))
    result = cursor.fetchone()

    if result:
        id_ = result[0]
        cache[cache_key] = id_
        return id_
    else:
        # Insert new value
        insert_sql = f"INSERT INTO {table_name} (name) VALUES (?)"
        cursor.execute(insert_sql, (value,))
        id_ = cursor.lastrowid
        cache[cache_key] = id_
        return id_

# --- NEW: Download Function ---
def download_if_newer(url, local_path):
    """
    Downloads a file from a URL only if it's newer than the local copy
    or if the local copy doesn't exist.

    Args:
        url (str): The URL to download from.
        local_path (str): The local path to save the file.

    Returns:
        bool: True if the file is ready for use (downloaded or up-to-date),
              False if an error occurred during download check or download.
    """
    print("-" * 40)
    print(f"Checking file: {os.path.basename(local_path)}")
    print(f"URL: {url}")

    local_mtime = None
    download_needed = False

    # 1. Check local file
    if os.path.exists(local_path):
        try:
            local_timestamp = os.path.getmtime(local_path)
            # Convert local time to UTC datetime object (naive)
            local_mtime = datetime.fromtimestamp(local_timestamp, tz=timezone.utc).replace(tzinfo=None)
            print(f"Local file exists. Last modified (UTC): {local_mtime}")
        except Exception as e:
            print(f"Warning: Could not get modification time for local file '{local_path}': {e}")
            # Proceed assuming download might be needed
            download_needed = True
    else:
        print("Local file does not exist.")
        download_needed = True

    # 2. Check remote file headers (if local file exists and we have its time)
    if not download_needed and local_mtime:
        try:
            print("Checking remote file modification date...")
            # Use HEAD request to get only headers
            response = requests.head(url, timeout=10) # Add a timeout
            response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)

            if 'Last-Modified' in response.headers:
                remote_last_modified_str = response.headers['Last-Modified']
                # Parse HTTP date string into datetime object
                remote_mtime = parsedate_to_datetime(remote_last_modified_str)

                # Ensure comparison is valid (make remote naive UTC if it's aware)
                if remote_mtime.tzinfo is not None:
                     remote_mtime = remote_mtime.astimezone(timezone.utc).replace(tzinfo=None)

                print(f"Remote file last modified (UTC): {remote_mtime}")

                if remote_mtime > local_mtime:
                    print("Remote file is newer.")
                    download_needed = True
                else:
                    print("Local file is up-to-date.")
                    # No download needed, file is ready
                    print("-" * 40)
                    return True
            else:
                print("Warning: 'Last-Modified' header not found on remote server. Downloading anyway.")
                download_needed = True

        except requests.exceptions.RequestException as e:
            print(f"Error checking remote file headers: {e}")
            print("Proceeding without download check. Will use existing local file if present.")
            # Don't force download if HEAD fails, maybe network is temp down
            # If local file exists, we'll use it. If not, import will fail later.
            return os.path.exists(local_path) # Return True only if local file exists
        except Exception as e:
            print(f"Error parsing remote modification date: {e}")
            print("Downloading anyway.")
            download_needed = True

    # 3. Download if needed
    if download_needed:
        print(f"Downloading file to '{local_path}'...")
        try:
            # Ensure the target directory exists
            os.makedirs(os.path.dirname(local_path), exist_ok=True)

            # Make GET request with streaming
            with requests.get(url, stream=True, timeout=30) as r: # Longer timeout for download
                r.raise_for_status()
                # Write to file in chunks
                with open(local_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
            print("Download complete.")
            print("-" * 40)
            return True # Download successful, file is ready

        except requests.exceptions.RequestException as e:
            print(f"Error downloading file: {e}")
            print("-" * 40)
            return False # Download failed
        except IOError as e:
            print(f"Error writing file '{local_path}': {e}")
            print("-" * 40)
            return False # File writing failed
        except Exception as e:
            print(f"An unexpected error occurred during download: {e}")
            print("-" * 40)
            return False # Other download error

    # Should only reach here if local file existed and was up-to-date
    print("-" * 40)
    return True


# --- Main Script ---

def main():
    print(f"Starting import process...")

    # --- NEW: Download Check ---
    if not download_if_newer(DOWNLOAD_URL, INPUT_FILE_PATH):
        print("Halting import process due to download error.")
        return # Stop if download failed

    # --- Check if input file exists after download attempt ---
    # This is crucial if download_if_newer returned False on HEAD error but local file didn't exist
    if not os.path.exists(INPUT_FILE_PATH):
         print(f"ERROR: Input file '{INPUT_FILE_PATH}' not found and download failed or wasn't attempted.")
         print("Please check the URL, network connection, and file permissions.")
         return

    print(f"Proceeding with import from '{INPUT_FILE_PATH}' to '{DATABASE_PATH}'...")

    # --- 0. Delete existing database file ---
    if os.path.exists(DATABASE_PATH):
        try:
            print(f"Deleting existing database: '{DATABASE_PATH}'...")
            os.remove(DATABASE_PATH)
            print("Existing database deleted successfully.")
        except OSError as e:
            print(f"Error deleting existing database file '{DATABASE_PATH}': {e}")
            print("Please check file permissions or close any applications using the database.")
            return # Stop the script if deletion fails

    # --- 1. Database Setup ---
    conn = None # Initialize conn outside try block for finally clause
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        print("Database connection established.")

        # Enable Foreign Keys enforcement
        cursor.execute("PRAGMA foreign_keys = ON;")

    except sqlite3.Error as e:
        print(f"Error connecting to database: {e}")
        if conn: conn.close() # Close connection if partially opened
        return
    except Exception as e:
        print(f"An unexpected error occurred during setup: {e}")
        if conn: conn.close()
        return

    # --- 2. Schema Creation ---
    try:
        print("Creating database schema...")

        # Create tables for normalized columns
        normalized_table_mapping = {} # Store original_col_name -> (normalized_table_name, normalized_col_name_id)
        for col_name in NORMALIZE_COLUMNS:
            clean_col_name = clean_sql_identifier(col_name)
            table_name = create_normalized_table_name(clean_col_name)
            if not table_name: # Check if table name generation failed
                print(f"Warning: Skipping normalization for column '{col_name}' due to invalid name.")
                continue
            col_name_id = f"{clean_col_name}_id"
            normalized_table_mapping[col_name] = (table_name, col_name_id)

            # Create table
            create_table_sql = f"""
            CREATE TABLE {table_name} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL
            );
            """
            cursor.execute(create_table_sql)
            print(f"  - Created normalized table: {table_name}")

        # Create the main table ('Emissionen')
        main_table_sql = "CREATE TABLE Emissionen (\n"
        column_definitions = []

        # Read header from file to define columns accurately
        try:
            # Use INPUT_FILE_PATH which points to the potentially downloaded file
            with codecs.open(INPUT_FILE_PATH, 'r', encoding=FILE_ENCODING, errors='replace') as infile:
                # Use csv reader to handle potential quoting and delimiters correctly
                reader = csv.reader(infile, delimiter=DELIMITER)
                header = next(reader) # Read the first row as header
                print(f"Read headers: {header}")
        except FileNotFoundError:
            # This check should ideally be redundant now due to checks after download_if_newer
            print(f"ERROR: Input file not found at '{INPUT_FILE_PATH}'")
            conn.close()
            return
        except Exception as e:
            print(f"Error reading header from file: {e}")
            conn.close()
            return

        original_headers = header[:] # Keep a copy of original headers
        cleaned_headers = [clean_sql_identifier(h) for h in header]
        header_map = dict(zip(original_headers, cleaned_headers)) # Map original to cleaned

        # Define columns for the main table
        for original_col, clean_col in header_map.items():
            if not clean_col: # Skip if cleaning resulted in empty name
                 print(f"Warning: Skipping column '{original_col}' due to invalid cleaned name.")
                 continue
            if original_col == "TG-Code": # Special handling for primary key
                 # Ensure TG_Code is TEXT as it might contain non-numeric chars
                column_definitions.append(f"    \"{clean_col}\" TEXT PRIMARY KEY NOT NULL") # Quote name just in case
            elif original_col in NORMALIZE_COLUMNS and original_col in normalized_table_mapping: # Check if it was successfully added to mapping
                table_name, col_name_id = normalized_table_mapping[original_col]
                column_definitions.append(f"    \"{col_name_id}\" INTEGER") # Quote name
                # Add foreign key constraint later after all columns are defined
            else:
                # Default to TEXT for other columns for robustness
                column_definitions.append(f"    \"{clean_col}\" TEXT") # Quote name

        # Add foreign key constraints
        for original_col in NORMALIZE_COLUMNS:
             # Check if the column actually exists in the file AND was successfully mapped
             if original_col in header_map and original_col in normalized_table_mapping:
                table_name, col_name_id = normalized_table_mapping[original_col]
                column_definitions.append(f"    FOREIGN KEY (\"{col_name_id}\") REFERENCES \"{table_name}\"(id)") # Quote names


        main_table_sql += ",\n".join(column_definitions)
        main_table_sql += "\n);"
        # print("\nMain table SQL:\n", main_table_sql) # Uncomment for debugging SQL
        cursor.execute(main_table_sql)
        print("  - Created main table: Emissionen")
        print("Schema creation complete.")

    except sqlite3.Error as e:
        print(f"Error creating schema: {e}")
        conn.rollback() # Rollback any partial schema changes
        conn.close()
        return
    except Exception as e:
        print(f"An unexpected error occurred during schema creation: {e}")
        conn.rollback()
        conn.close()
        return

    # --- 3. Data Import ---
    print("Starting data import process...")
    normalization_cache = {} # Cache for normalized IDs: {(table_name, value): id}
    inserted_count = 0
    skipped_count = 0

    try:
        # Use INPUT_FILE_PATH which points to the potentially downloaded file
        with codecs.open(INPUT_FILE_PATH, 'r', encoding=FILE_ENCODING, errors='replace') as infile:
            reader = csv.reader(infile, delimiter=DELIMITER)
            next(reader) # Skip header row again

            # Prepare insert statement for the main table
            main_table_cols_quoted = []
            placeholders = []
            original_headers_for_insert = [] # Keep track of which headers we are inserting

            for original_col in original_headers:
                # Skip columns that resulted in an empty cleaned name during schema creation
                clean_col = header_map.get(original_col)
                if not clean_col:
                    continue

                if original_col == "TG-Code":
                    main_table_cols_quoted.append(f'"{clean_col}"') # Quote name
                    placeholders.append("?")
                    original_headers_for_insert.append(original_col)
                elif original_col in NORMALIZE_COLUMNS and original_col in normalized_table_mapping: # Check if normalized and mapped
                    _, col_name_id = normalized_table_mapping[original_col]
                    main_table_cols_quoted.append(f'"{col_name_id}"') # Quote name
                    placeholders.append("?")
                    original_headers_for_insert.append(original_col) # Use original to fetch data
                else:
                    main_table_cols_quoted.append(f'"{clean_col}"') # Quote name
                    placeholders.append("?")
                    original_headers_for_insert.append(original_col)

            # Use INSERT OR REPLACE to overwrite rows with the same PRIMARY KEY
            insert_sql = f"INSERT OR REPLACE INTO Emissionen ({', '.join(main_table_cols_quoted)}) VALUES ({', '.join(placeholders)})"

            # Process rows
            for i, row in enumerate(reader):
                if len(row) != len(original_headers):
                    print(f"Warning: Skipping row {i+2} due to incorrect number of columns (expected {len(original_headers)}, got {len(row)}). Row data: {row}")
                    skipped_count += 1
                    continue

                # Create dictionary for easier access by original header name
                row_data = dict(zip(original_headers, row))

                # Prepare values for insertion
                values_to_insert = []
                try:
                    for original_col in original_headers_for_insert: # Iterate through cols we are actually inserting
                        value = row_data.get(original_col, None) # Get value using original header

                        if original_col == "TG-Code":
                            if not value: # TG-Code cannot be empty as it's PK
                                raise ValueError(f"TG-Code is empty in row {i+2}")
                            values_to_insert.append(value)
                        elif original_col in NORMALIZE_COLUMNS and original_col in normalized_table_mapping: # Check if normalized and mapped
                            table_name, _ = normalized_table_mapping[original_col]
                            normalized_id = get_or_insert_normalized_id(cursor, table_name, value, normalization_cache)
                            values_to_insert.append(normalized_id)
                        else:
                            values_to_insert.append(value if value is not None else '')

                    # Execute insert for the main table row
                    cursor.execute(insert_sql, tuple(values_to_insert))
                    inserted_count += 1

                    # Commit periodically for large files (e.g., every 1000 rows)
                    if (i + 1) % 1000 == 0:
                        conn.commit()
                        print(f"  ... committed {inserted_count} rows ...")

                except ValueError as ve:
                     print(f"Error processing row {i+2}: {ve}. Skipping row. Data: {row}")
                     skipped_count += 1
                     conn.rollback() # Rollback the failed transaction segment
                     normalization_cache.clear() # Clear cache after rollback
                     cursor.execute("PRAGMA foreign_keys = ON;") # Re-enable FKs if needed
                     continue # Skip this row
                except sqlite3.IntegrityError as ie:
                    print(f"Integrity error inserting row {i+2}: {ie}. Skipping row. Data: {row}")
                    skipped_count += 1
                    conn.rollback() # Rollback the failed transaction segment
                    normalization_cache.clear() # Clear cache after rollback
                    cursor.execute("PRAGMA foreign_keys = ON;") # Re-enable FKs if needed
                    continue # Skip this row
                except Exception as e:
                    print(f"Unexpected error processing row {i+2}: {e}. Skipping row. Data: {row}")
                    skipped_count += 1
                    conn.rollback() # Rollback potential partial transaction state
                    normalization_cache.clear() # Clear cache after rollback
                    cursor.execute("PRAGMA foreign_keys = ON;") # Re-enable FKs if needed
                    continue # Skip this row


        # Final commit
        conn.commit()
        print(f"Data import complete. Inserted {inserted_count} rows.")
        if skipped_count > 0:
            print(f"Skipped {skipped_count} rows due to errors.")

    except FileNotFoundError:
        # Should be less likely now, but keep as a safeguard
        print(f"ERROR: Input file not found at '{INPUT_FILE_PATH}' during import phase.")
    except sqlite3.Error as e:
        print(f"Database error during data import: {e}")
        if conn: conn.rollback() # Rollback if error occurs during import loop
    except Exception as e:
        print(f"An unexpected error occurred during data import: {e}")
        if conn: conn.rollback()
    finally:
        # --- 4. Cleanup ---
        if conn:
            conn.close()
            print("Database connection closed.")

if __name__ == "__main__":
    # Create data directory if it doesn't exist (needed for download target)
    if not os.path.exists(DATA_DIR):
        try:
            os.makedirs(DATA_DIR)
            print(f"Created data directory: '{DATA_DIR}'")
        except OSError as e:
            print(f"Error creating data directory '{DATA_DIR}': {e}")
            # Decide if you want to exit if directory creation fails
            # exit()

    # Run the main import process which now includes the download check
    main()

