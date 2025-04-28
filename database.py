# database.py
import sqlite3
import os
import csv
import codecs

# Import constants and utils
import config
from utils import clean_sql_identifier, create_normalized_table_name

# --- Database Connection ---
def get_db_connection():
    """Establishes and returns a database connection."""
    try:
        conn = sqlite3.connect(config.DATABASE_PATH)
        conn.row_factory = sqlite3.Row # Return rows as dictionary-like objects
        conn.execute("PRAGMA foreign_keys = ON;") # Enforce foreign key constraints
        return conn
    except sqlite3.Error as e:
        print(f"Database connection error: {e}")
        raise # Re-raise the exception

# --- Schema Management ---
def create_schema(cursor):
    """Creates the necessary tables in the database."""
    print("Creating database schema...")
    normalized_table_mapping = {} # Store mapping for FK constraints

    # 1. Create Normalized Tables
    for col_name in config.NORMALIZE_COLUMNS:
        clean_col_name = clean_sql_identifier(col_name)
        table_name = create_normalized_table_name(clean_col_name)
        if not table_name: continue
        col_name_id = f"{clean_col_name}_id"
        normalized_table_mapping[col_name] = (table_name, col_name_id)

        create_table_sql = f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        );
        """
        cursor.execute(create_table_sql)
        # print(f"  - Ensured normalized table exists: {table_name}") # Less verbose

    # 2. Create Main 'Emissionen' Table
    main_table_sql = "CREATE TABLE IF NOT EXISTS Emissionen (\n"
    column_definitions = []

    # Read header from the source file to define columns
    try:
        with codecs.open(config.INPUT_FILE_PATH, 'r', encoding=config.FILE_ENCODING, errors='replace') as infile:
            reader = csv.reader(infile, delimiter=config.DELIMITER)
            header = next(reader)
    except FileNotFoundError:
        raise FileNotFoundError(f"Input file not found at {config.INPUT_FILE_PATH} for schema creation.")
    except Exception as e:
        raise IOError(f"Error reading header from file: {e}")

    original_headers = header[:] # Keep original names for mapping
    cleaned_headers = [clean_sql_identifier(h) for h in header]
    header_map = dict(zip(original_headers, cleaned_headers)) # Map original -> cleaned

    # Define columns based on header
    for original_col, clean_col in header_map.items():
        if not clean_col: continue # Skip if cleaning resulted in empty string

        col_type = "TEXT" # Default type
        constraints = ""

        if original_col == "TG-Code": # Assuming TG-Code is the primary key
            constraints = "PRIMARY KEY NOT NULL"
        elif original_col in config.NORMALIZE_COLUMNS and original_col in normalized_table_mapping:
            # This column will be replaced by its ID
            _, col_name_id = normalized_table_mapping[original_col]
            column_definitions.append(f"    \"{col_name_id}\" INTEGER") # Add the ID column
            continue # Skip adding the original text column definition
        # Add more type checks here if needed (e.g., for numeric columns)

        column_definitions.append(f"    \"{clean_col}\" {col_type} {constraints}".strip())

    # Add Foreign Key constraints after all column definitions
    for original_col in config.NORMALIZE_COLUMNS:
         if original_col in header_map and original_col in normalized_table_mapping:
            table_name, col_name_id = normalized_table_mapping[original_col]
            column_definitions.append(f"    FOREIGN KEY (\"{col_name_id}\") REFERENCES \"{table_name}\"(id)")

    main_table_sql += ",\n".join(column_definitions)
    main_table_sql += "\n);"

    # Drop existing table if it exists before creating
    cursor.execute("DROP TABLE IF EXISTS Emissionen;")
    cursor.execute(main_table_sql)
    print("Schema creation complete.")
    return header_map, normalized_table_mapping # Return mappings needed for insertion

# --- Data Insertion ---
def get_or_insert_normalized_id(cursor, table_name, value, cache):
    """Gets the ID for a value in a normalized table, inserting if needed."""
    if value is None or value == '':
        value = '(leer)' # Use placeholder for empty/null values

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
        try:
            cursor.execute(insert_sql, (value,))
            id_ = cursor.lastrowid
            cache[cache_key] = id_
            return id_
        except sqlite3.IntegrityError:
            # Handle rare race condition or unexpected unique constraint violation
            print(f"Warning: Integrity error inserting '{value}' into {table_name}. Re-fetching ID.")
            cursor.execute(select_sql, (value,)) # Re-fetch after potential concurrent insert
            result = cursor.fetchone()
            if result:
                 id_ = result[0]
                 cache[cache_key] = id_
                 return id_
            else:
                 # This shouldn't happen if IntegrityError occurred, but raise if it does
                 raise ValueError(f"Could not get or insert ID for '{value}' in {table_name} after IntegrityError.")


def insert_data(conn, reader, header_map, normalized_table_mapping, total_rows, progress_callback=None):
    """Inserts data from the CSV reader into the Emissionen table."""
    cursor = conn.cursor()
    normalization_cache = {}
    inserted_count = 0
    skipped_count = 0
    progress_update_frequency = max(1, total_rows // 100) if total_rows > 0 else 100 # Update frequency

    original_headers = list(header_map.keys())

    # Prepare INSERT statement dynamically based on header_map and normalized_mapping
    main_table_cols_quoted = []
    placeholders = []
    original_headers_for_insert_order = [] # Maintain order for value extraction

    for original_col in original_headers:
        clean_col = header_map.get(original_col)
        if not clean_col: continue # Skip if column was invalid

        if original_col in config.NORMALIZE_COLUMNS and original_col in normalized_table_mapping:
            # Use the ID column name
            _, col_name_id = normalized_table_mapping[original_col]
            main_table_cols_quoted.append(f'"{col_name_id}"')
        else:
            # Use the cleaned column name
            main_table_cols_quoted.append(f'"{clean_col}"')

        placeholders.append("?")
        original_headers_for_insert_order.append(original_col) # Keep track of which original col corresponds to placeholder

    insert_sql = f"INSERT OR REPLACE INTO Emissionen ({', '.join(main_table_cols_quoted)}) VALUES ({', '.join(placeholders)})"
    # print(f"DEBUG Insert SQL: {insert_sql}") # Optional debug

    for i, row in enumerate(reader):
        current_row_num = i + 1 # 1-based index for progress reporting

        if len(row) != len(original_headers):
            print(f"Warning: Skipping row {current_row_num+1} due to incorrect number of columns (expected {len(original_headers)}, got {len(row)}).")
            skipped_count += 1
            continue

        row_data = dict(zip(original_headers, row)) # Map current row values by original header name
        values_to_insert = []

        try:
            # Build the list of values in the correct order for the INSERT statement
            for original_col in original_headers_for_insert_order:
                value = row_data.get(original_col) # Get value using original header name

                if original_col == "TG-Code":
                    if not value: raise ValueError(f"TG-Code is empty in row {current_row_num+1}")
                    values_to_insert.append(value)
                elif original_col in config.NORMALIZE_COLUMNS and original_col in normalized_table_mapping:
                    table_name, _ = normalized_table_mapping[original_col]
                    normalized_id = get_or_insert_normalized_id(cursor, table_name, value, normalization_cache)
                    values_to_insert.append(normalized_id)
                else:
                    # For non-normalized columns, insert the value directly (or empty string)
                    values_to_insert.append(value if value is not None else '')

            # Execute the insert
            cursor.execute(insert_sql, tuple(values_to_insert))
            inserted_count += 1

            # Call progress callback periodically
            if progress_callback and (current_row_num % progress_update_frequency == 0 or current_row_num == total_rows):
                progress_callback(current_row=current_row_num, total_rows=total_rows)

            # Commit periodically
            if current_row_num % 5000 == 0:
                conn.commit()
                # print(f"  ... committed {inserted_count} rows ...") # Less verbose

        except (ValueError, sqlite3.IntegrityError) as data_err:
            print(f"Error processing row {current_row_num+1}: {data_err}. Skipping.")
            skipped_count += 1
            conn.rollback() # Rollback transaction for the failed row
            # No need to clear cache or reset PRAGMA here, just continue
        except Exception as e:
            print(f"Unexpected error processing row {current_row_num+1}: {e}. Skipping.")
            skipped_count += 1
            conn.rollback()

    # Final commit for any remaining rows
    conn.commit()

    # Final progress update
    if progress_callback:
        progress_callback(current_row=total_rows, total_rows=total_rows)

    print(f"Data import complete. Inserted {inserted_count} rows.")
    if skipped_count > 0:
        print(f"Skipped {skipped_count} rows due to errors.")

# --- Data Querying ---
def search_by_tg_code(tg_code_to_search):
    """Searches the database for a TG-Code and returns the raw data row."""
    if not os.path.exists(config.DATABASE_PATH):
        print(f"Error: Database file '{config.DATABASE_PATH}' not found.")
        return None # Return None if DB doesn't exist

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Dynamically build the SELECT query with JOINs for normalized columns
        select_parts = ["e.*"] # Select all columns from the main table first
        join_parts = []
        normalized_mapping_for_query = {} # To reconstruct normalized values if needed

        # Re-create the mapping needed for the query (similar to schema creation)
        for i, original_col in enumerate(config.NORMALIZE_COLUMNS):
            clean_base = clean_sql_identifier(original_col)
            if not clean_base: continue
            table_name = create_normalized_table_name(clean_base)
            if not table_name: continue

            id_col_in_emissionen = f"{clean_base}_id"
            table_alias = f"t{i}"
            # Select the 'name' from the normalized table, aliasing it back to the original column name
            # Use quotes around the alias if the original name needs them
            name_alias = original_col
            select_parts.append(f'{table_alias}.name AS "{name_alias}"')
            join_parts.append(
                f'LEFT JOIN {table_name} {table_alias} ON e."{id_col_in_emissionen}" = {table_alias}.id'
            )
            normalized_mapping_for_query[original_col] = (table_name, id_col_in_emissionen, name_alias)

        # Construct the full query
        query = f"""
            SELECT {', '.join(select_parts)}
            FROM Emissionen e
            {' '.join(join_parts)}
            WHERE e."{clean_sql_identifier('TG-Code')}" = ?
        """
        # print(f"DEBUG Search Query: {query}") # Optional debug

        cursor.execute(query, (tg_code_to_search,))
        result = cursor.fetchone() # fetchone returns a Row object or None

        return result if result else None # Return the Row object directly or None

    except sqlite3.Error as e:
        print(f"Database error during search for '{tg_code_to_search}': {e}")
        return None # Return None on error
    except Exception as e:
        print(f"An unexpected error occurred during search: {e}")
        return None # Return None on error
    finally:
        if conn:
            conn.close()

