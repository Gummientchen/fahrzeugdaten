# import.py
import sqlite3
import csv
import os
import codecs
import re

# --- Configuration ---
INPUT_FILE_PATH = os.path.join('data', 'emissionen.txt')
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

# --- Main Script ---

def main():
    print(f"Starting import from '{INPUT_FILE_PATH}' to '{DATABASE_PATH}'...")

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

            # Drop table if exists (redundant now but harmless)
            # cursor.execute(f"DROP TABLE IF EXISTS {table_name};")
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
        # cursor.execute("DROP TABLE IF EXISTS Emissionen;") # Redundant now but harmless
        main_table_sql = "CREATE TABLE Emissionen (\n"
        column_definitions = []

        # Read header from file to define columns accurately
        try:
            with codecs.open(INPUT_FILE_PATH, 'r', encoding=FILE_ENCODING, errors='replace') as infile:
                # Use csv reader to handle potential quoting and delimiters correctly
                reader = csv.reader(infile, delimiter=DELIMITER)
                header = next(reader) # Read the first row as header
                print(f"Read headers: {header}")
        except FileNotFoundError:
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
                # Could refine types (INTEGER, REAL) if data quality is guaranteed
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

            # print("\nInsert SQL:", insert_sql) # Uncomment for debugging
            # print("Columns for insert:", main_table_cols_quoted)
            # print("Original headers for insert:", original_headers_for_insert)


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
                            # For non-normalized columns, insert the value directly (as TEXT)
                            # Handle potential None values if necessary, though csv usually reads empty strings
                            values_to_insert.append(value if value is not None else '')

                    # Execute insert for the main table row
                    # print(f"Inserting row {i+2}: {values_to_insert}") # Uncomment for debugging
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
                    # This should be less common now with INSERT OR REPLACE for PK,
                    # but could happen for UNIQUE constraints in normalized tables or FK issues
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
        # This case should have been caught earlier, but added for robustness
        print(f"ERROR: Input file not found at '{INPUT_FILE_PATH}'")
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
    # Create data directory if it doesn't exist (for testing convenience)
    if not os.path.exists('data'):
        os.makedirs('data')
        print("Created 'data' directory. Please place 'emissionen.txt' inside it.")
        # You might want to exit here if the file definitely won't exist yet
        # exit()

    # Check if input file exists before running main
    if not os.path.exists(INPUT_FILE_PATH):
         print(f"ERROR: Input file '{INPUT_FILE_PATH}' not found. Please ensure it exists.")
    else:
        main()
