# importer.py
import sqlite3
import csv
import os
import codecs
import re
import sys
import requests # For downloading
from datetime import datetime, timezone # For date comparison
from email.utils import parsedate_to_datetime # For parsing HTTP dates

# --- Configuration ---
DOWNLOAD_URL = "https://opendata.astra.admin.ch/ivzod/2000-Typengenehmigungen_TG_TARGA/2200-Basisdaten_TG_ab_1995/emissionen.txt"
DATA_DIR = "data"
INPUT_FILENAME = "emissionen.txt"
INPUT_FILE_PATH = os.path.join(DATA_DIR, INPUT_FILENAME)
DATABASE_PATH = 'emissionen.db'
FILE_ENCODING = 'windows-1252'
DB_ENCODING = 'utf-8'
DELIMITER = '\t'

NORMALIZE_COLUMNS = [
    "Marke", "Getriebe", "Motormarke", "Motortyp", "Treibstoff",
    "Abgasreinigung", "Antrieb", "Anzahl_Achsen_Räder", "AbgasCode",
    "Emissionscode", "GeräuschCode"
]

# --- Helper Functions ---
# clean_sql_identifier, create_normalized_table_name, get_or_insert_normalized_id remain the same
def clean_sql_identifier(name):
    if not isinstance(name, str): return ""
    name = re.sub(r'[ /.\-+()]+', '_', name)
    name = name.strip('_')
    if name and name[0].isdigit(): name = '_' + name
    return name

def create_normalized_table_name(base_name):
    clean_name = clean_sql_identifier(base_name)
    if not clean_name: return None
    if clean_name.endswith('e'): return f"{clean_name}n"
    elif clean_name.endswith('s'): return f"{clean_name}es"
    else: return f"{clean_name}s"

def get_or_insert_normalized_id(cursor, table_name, value, cache):
    if value is None or value == '': value = '(leer)'
    cache_key = (table_name, value)
    if cache_key in cache: return cache[cache_key]
    select_sql = f"SELECT id FROM {table_name} WHERE name = ?"
    cursor.execute(select_sql, (value,))
    result = cursor.fetchone()
    if result:
        id_ = result[0]
        cache[cache_key] = id_
        return id_
    else:
        insert_sql = f"INSERT INTO {table_name} (name) VALUES (?)"
        cursor.execute(insert_sql, (value,))
        id_ = cursor.lastrowid
        cache[cache_key] = id_
        return id_

# download_if_newer remains the same
def download_if_newer(url, local_path):
    print("-" * 40)
    print(f"Checking file: {os.path.basename(local_path)}")
    print(f"URL: {url}")
    local_mtime = None
    download_needed = False
    if os.path.exists(local_path):
        try:
            local_timestamp = os.path.getmtime(local_path)
            local_mtime = datetime.fromtimestamp(local_timestamp, tz=timezone.utc).replace(tzinfo=None)
            print(f"Local file exists. Last modified (UTC): {local_mtime}")
        except Exception as e:
            print(f"Warning: Could not get modification time for local file '{local_path}': {e}")
            download_needed = True
    else:
        print("Local file does not exist.")
        download_needed = True

    if not download_needed and local_mtime:
        try:
            print("Checking remote file modification date...")
            response = requests.head(url, timeout=10)
            response.raise_for_status()
            if 'Last-Modified' in response.headers:
                remote_last_modified_str = response.headers['Last-Modified']
                remote_mtime = parsedate_to_datetime(remote_last_modified_str)
                if remote_mtime.tzinfo is not None:
                     remote_mtime = remote_mtime.astimezone(timezone.utc).replace(tzinfo=None)
                print(f"Remote file last modified (UTC): {remote_mtime}")
                if remote_mtime > local_mtime:
                    print("Remote file is newer.")
                    download_needed = True
                else:
                    print("Local file is up-to-date.")
                    print("-" * 40)
                    return True
            else:
                print("Warning: 'Last-Modified' header not found. Downloading anyway.")
                download_needed = True
        except requests.exceptions.RequestException as e:
            print(f"Error checking remote file headers: {e}")
            print("Proceeding without download check. Will use existing local file if present.")
            return os.path.exists(local_path)
        except Exception as e:
            print(f"Error parsing remote modification date: {e}")
            print("Downloading anyway.")
            download_needed = True

    if download_needed:
        print(f"Downloading file to '{local_path}'...")
        try:
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            with requests.get(url, stream=True, timeout=60) as r: # Increased timeout
                r.raise_for_status()
                with open(local_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
            print("Download complete.")
            print("-" * 40)
            return True
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
    print("-" * 40)
    return True


# --- Main Script (MODIFIED) ---

# *** ADD progress_callback parameter ***
def main(progress_callback=None):
    print(f"Starting import process...")

    if not download_if_newer(DOWNLOAD_URL, INPUT_FILE_PATH):
        print("Halting import process due to download error.")
        # *** Raise an exception instead of just returning ***
        raise requests.exceptions.RequestException("Download failed or file check error.")

    if not os.path.exists(INPUT_FILE_PATH):
         msg = f"Input file '{INPUT_FILE_PATH}' not found after download check."
         print(f"ERROR: {msg}")
         # *** Raise an exception ***
         raise FileNotFoundError(msg)

    print(f"Proceeding with import from '{INPUT_FILE_PATH}' to '{DATABASE_PATH}'...")

    if os.path.exists(DATABASE_PATH):
        try:
            print(f"Deleting existing database: '{DATABASE_PATH}'...")
            os.remove(DATABASE_PATH)
            print("Existing database deleted successfully.")
        except OSError as e:
            msg = f"Error deleting existing database file '{DATABASE_PATH}': {e}"
            print(msg)
            # *** Raise an exception ***
            raise OSError(msg)

    conn = None
    total_rows = 0 # *** Initialize total_rows ***
    try:
        # --- Count total rows for progress bar ---
        print("Counting total rows in input file...")
        try:
            with codecs.open(INPUT_FILE_PATH, 'r', encoding=FILE_ENCODING, errors='replace') as infile:
                reader = csv.reader(infile, delimiter=DELIMITER)
                header = next(reader) # Read header
                # Sum remaining lines
                total_rows = sum(1 for row in reader)
            print(f"Found {total_rows} data rows.")
        except Exception as e:
            print(f"Warning: Could not accurately count rows: {e}. Progress bar may be inaccurate or indeterminate.")
            total_rows = 0 # Reset if counting failed

        # --- Database Setup ---
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        print("Database connection established.")
        cursor.execute("PRAGMA foreign_keys = ON;")

        # --- Schema Creation ---
        print("Creating database schema...")
        normalized_table_mapping = {}
        for col_name in NORMALIZE_COLUMNS:
            clean_col_name = clean_sql_identifier(col_name)
            table_name = create_normalized_table_name(clean_col_name)
            if not table_name: continue
            col_name_id = f"{clean_col_name}_id"
            normalized_table_mapping[col_name] = (table_name, col_name_id)
            create_table_sql = f"CREATE TABLE {table_name} (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL);"
            cursor.execute(create_table_sql)
            # print(f"  - Created normalized table: {table_name}") # Less verbose

        main_table_sql = "CREATE TABLE Emissionen (\n"
        column_definitions = []
        try:
            with codecs.open(INPUT_FILE_PATH, 'r', encoding=FILE_ENCODING, errors='replace') as infile:
                reader = csv.reader(infile, delimiter=DELIMITER)
                header = next(reader)
        except Exception as e:
            raise IOError(f"Error re-reading header from file: {e}")

        original_headers = header[:]
        cleaned_headers = [clean_sql_identifier(h) for h in header]
        header_map = dict(zip(original_headers, cleaned_headers))

        for original_col, clean_col in header_map.items():
            if not clean_col: continue
            if original_col == "TG-Code":
                column_definitions.append(f"    \"{clean_col}\" TEXT PRIMARY KEY NOT NULL")
            elif original_col in NORMALIZE_COLUMNS and original_col in normalized_table_mapping:
                _, col_name_id = normalized_table_mapping[original_col]
                column_definitions.append(f"    \"{col_name_id}\" INTEGER")
            else:
                column_definitions.append(f"    \"{clean_col}\" TEXT")

        for original_col in NORMALIZE_COLUMNS:
             if original_col in header_map and original_col in normalized_table_mapping:
                table_name, col_name_id = normalized_table_mapping[original_col]
                column_definitions.append(f"    FOREIGN KEY (\"{col_name_id}\") REFERENCES \"{table_name}\"(id)")

        main_table_sql += ",\n".join(column_definitions)
        main_table_sql += "\n);"
        cursor.execute(main_table_sql)
        print("Schema creation complete.")

        # --- Data Import ---
        print("Starting data import process...")
        normalization_cache = {}
        inserted_count = 0
        skipped_count = 0
        # *** Define update frequency ***
        progress_update_frequency = max(1, total_rows // 100) # Update ~100 times, but at least every row if < 100 rows

        with codecs.open(INPUT_FILE_PATH, 'r', encoding=FILE_ENCODING, errors='replace') as infile:
            reader = csv.reader(infile, delimiter=DELIMITER)
            next(reader) # Skip header

            main_table_cols_quoted = []
            placeholders = []
            original_headers_for_insert = []
            for original_col in original_headers:
                clean_col = header_map.get(original_col)
                if not clean_col: continue
                if original_col == "TG-Code":
                    main_table_cols_quoted.append(f'"{clean_col}"')
                    placeholders.append("?")
                    original_headers_for_insert.append(original_col)
                elif original_col in NORMALIZE_COLUMNS and original_col in normalized_table_mapping:
                    _, col_name_id = normalized_table_mapping[original_col]
                    main_table_cols_quoted.append(f'"{col_name_id}"')
                    placeholders.append("?")
                    original_headers_for_insert.append(original_col)
                else:
                    main_table_cols_quoted.append(f'"{clean_col}"')
                    placeholders.append("?")
                    original_headers_for_insert.append(original_col)
            insert_sql = f"INSERT OR REPLACE INTO Emissionen ({', '.join(main_table_cols_quoted)}) VALUES ({', '.join(placeholders)})"

            for i, row in enumerate(reader):
                current_row_num = i + 1 # 1-based index for progress reporting
                if len(row) != len(original_headers):
                    print(f"Warning: Skipping row {current_row_num+1} due to incorrect number of columns.")
                    skipped_count += 1
                    continue

                row_data = dict(zip(original_headers, row))
                values_to_insert = []
                try:
                    for original_col in original_headers_for_insert:
                        value = row_data.get(original_col, None)
                        if original_col == "TG-Code":
                            if not value: raise ValueError(f"TG-Code is empty in row {current_row_num+1}")
                            values_to_insert.append(value)
                        elif original_col in NORMALIZE_COLUMNS and original_col in normalized_table_mapping:
                            table_name, _ = normalized_table_mapping[original_col]
                            normalized_id = get_or_insert_normalized_id(cursor, table_name, value, normalization_cache)
                            values_to_insert.append(normalized_id)
                        else:
                            values_to_insert.append(value if value is not None else '')

                    cursor.execute(insert_sql, tuple(values_to_insert))
                    inserted_count += 1

                    # *** Call progress callback periodically ***
                    if progress_callback and (current_row_num % progress_update_frequency == 0 or current_row_num == total_rows):
                        progress_callback(current_row=current_row_num, total_rows=total_rows)

                    if current_row_num % 5000 == 0: # Commit less frequently
                        conn.commit()
                        # print(f"  ... committed {inserted_count} rows ...") # Less verbose

                except (ValueError, sqlite3.IntegrityError) as data_err:
                    print(f"Error processing row {current_row_num+1}: {data_err}. Skipping.")
                    skipped_count += 1
                    conn.rollback()
                    normalization_cache.clear()
                    cursor.execute("PRAGMA foreign_keys = ON;")
                    continue
                except Exception as e:
                    print(f"Unexpected error processing row {current_row_num+1}: {e}. Skipping.")
                    skipped_count += 1
                    conn.rollback()
                    normalization_cache.clear()
                    cursor.execute("PRAGMA foreign_keys = ON;")
                    continue

        # *** Final progress update ***
        if progress_callback:
            progress_callback(current_row=total_rows, total_rows=total_rows)

        conn.commit()
        print(f"Data import complete. Inserted {inserted_count} rows.")
        if skipped_count > 0:
            print(f"Skipped {skipped_count} rows due to errors.")

    # --- Exception Handling for outer try block ---
    except (sqlite3.Error, IOError, OSError, requests.exceptions.RequestException) as e:
        print(f"An error occurred during the import process: {e}")
        if conn: conn.rollback()
        # *** Re-raise the exception so gui.py can catch it ***
        raise e
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        if conn: conn.rollback()
        # *** Re-raise the exception ***
        raise e
    finally:
        if conn:
            conn.close()
            print("Database connection closed.")

# --- Main Execution Guard ---
if __name__ == "__main__":
    if not os.path.exists(DATA_DIR):
        try:
            os.makedirs(DATA_DIR)
            print(f"Created data directory: '{DATA_DIR}'")
        except OSError as e:
            print(f"Error creating data directory '{DATA_DIR}': {e}")
            # Exit if directory creation fails, as download needs it
            sys.exit(1)
    try:
        # Example of calling main without a callback for standalone execution
        main()
    except Exception as e:
         # Catch exceptions raised by main() when run standalone
         print(f"Import process failed: {e}")
         sys.exit(1)

