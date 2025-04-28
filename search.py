# search.py
import sqlite3
import sys
import os
import re
from datetime import datetime # Import datetime module

# --- Configuration ---
DATABASE_PATH = 'emissionen.db'
# These should match the ones used in import.py
# We need them to know which columns were normalized and need joining
NORMALIZE_COLUMNS_ORIGINAL = [
    "Marke", "Getriebe", "Motormarke", "Motortyp", "Treibstoff",
    "Abgasreinigung", "Antrieb", "Anzahl_Achsen_Räder", "AbgasCode",
    "Emissionscode", "GeräuschCode"
]

# Dictionary mapping column names (as stored in DB) to units
# Use the cleaned SQL identifier names here
UNITS_MAP = {
    "Leergewicht_von": "kg",
    "Leergewicht_bis": "kg",
    "Garantiegewicht_von": "kg",
    "Garantiegewicht_bis": "kg",
    "Gesamtzuggewicht_bis": "kg",
    "Gesamtzuggewicht_von": "kg",
    "Vmax_von": "km/h",
    "Vmax_bis": "km/h",
    "Hubraum": "ccm",
    "Leistung": "kW",
    "Leistung_bei_n_min": "rpm",
    "Drehmoment": "Nm",
    "Drehmoment_bei_n_min": "rpm",
    "Fahrgeräusch": "dbA",
    "Standgeräusch": "dbA",
    "Standgeräusch_bei_n_min": "rpm"
    # Add any other columns with units if needed
}

# Assumed input format for Homologationsdatum (e.g., YYYYMMDD)
# Adjust this if your data uses a different format
HOMOLOGATIONSDATUM_INPUT_FORMAT = '%Y%m%d'
# Desired output format (e.g., DD.MM.YYYY)
HOMOLOGATIONSDATUM_OUTPUT_FORMAT = '%d.%m.%Y'

# --- Columns to Omit from Output ---
# Note: Corrected missing comma between ZT_NMHC and ZT_NOx
OMIT_COLUMNS_ORIGINAL = [
    "ET_CO", "ET_NMHC", "ET_NOx", "ET_PA", "ET_PA_Exp", "ET_PM",
    "ET_THC", "ET_THC_NOx", "ET_T_IV_THC", "ET_T_VI_CO", "ET_T_VI_THC",
    "ScCo2", "ScConsumption", "ScNh3", "ScNo2", "TC_CO2", "TC_Consumption",
    "TC_NH3", "TC_NO2", "ZT_CO", "ZT_NMHC", "ZT_NOx", "ZT_PA", "ZT_PA_Exp",
    "ZT_PM", "ZT_THC", "ZT_THC_NOx", "ZT_T_IV_THC", "ZT_T_VI_CO", "ZT_T_VI_THC",
    "ZT_NMHC", "ZT_NOx", "ZT_AbgasCode"
]

# --- Desired Display Order with Dividers ---
# Use original column names as expected in the output or from the source file
# Use a special marker for dividers
# *** MODIFIED: Use TG_Code (underscore) here ***
DIVIDER_MARKER = "---"
DISPLAY_ORDER_WITH_DIVIDERS = [
    "TG_Code", # Use underscore to match DB column name
    "Marke",
    "Typ",
    "Homologationsdatum",
    "Antrieb",
    "Hubraum",
    "Treibstoff",
    DIVIDER_MARKER,
    "Drehmoment",
    "Drehmoment_bei_n_min",
    "Leistung",
    "Leistung_bei_n_min",
    DIVIDER_MARKER,
    "Leergewicht_bis",
    "Leergewicht_von",
    "Garantiegewicht_von",
    DIVIDER_MARKER,
    "Vmax_bis",
    "Vmax_von",
    DIVIDER_MARKER,
    "Fahrgeräusch",
    "Standgeräusch",
    "Standgeräusch_bei_n_min",
    "GeräuschCode",
    DIVIDER_MARKER,
    "Anz_Zylinder",
    "Getriebe",
    "Motormarke",
    "Motortyp",
    "Takte",
    "iAchse",
    "AbgasCode",
    "Abgasreinigung",
    "Anzahl_Achsen_Räder",
    "Bauart",
    "Bemerkung",
    "Emissionscode",
    "Garantiegewicht_bis",
    "Gesamtzuggewicht_bis",
    "Gesamtzuggewicht_von"
]


# --- Helper Functions (copied/adapted from import.py for consistency) ---

def clean_sql_identifier(name):
    """Cleans a string to be a valid SQL identifier (table/column name)."""
    if not isinstance(name, str): # Handle potential non-string input
        return ""
    # Replace problematic characters with underscores FIRST
    name = re.sub(r'[ /.\-+()]+', '_', name)
    # Then handle specific known patterns like ET_THC_NOx
    # Make sure the specific replacement handles the '+' correctly if regex missed it
    name = name.replace('ET_THC_NOx', 'ET_THC_NOx')
    name = name.replace('ZT_THC_NOx', 'ZT_THC_NOx')
    # Remove trailing underscores
    name = name.strip('_')
    # Ensure it doesn't start with a number
    if name and name[0].isdigit():
        name = '_' + name
    return name

# Create a set of cleaned names for faster lookup for omitting columns
OMIT_COLUMNS_CLEANED = set(clean_sql_identifier(col) for col in OMIT_COLUMNS_ORIGINAL)
# print(f"DEBUG: Columns to omit (cleaned): {OMIT_COLUMNS_CLEANED}") # Optional: for debugging

def create_normalized_table_name(base_name):
    """Creates a pluralized table name for normalized columns."""
    clean_name = clean_sql_identifier(base_name)
    if not clean_name: return None # Handle empty base_name
    if clean_name.endswith('e'):
         return f"{clean_name}n"
    elif clean_name.endswith('s'):
        return f"{clean_name}es"
    else:
        return f"{clean_name}s"

# --- Main Search Function ---
# (No changes needed in search_by_tg_code function itself)
def search_by_tg_code(tg_code_to_search):
    """Searches the database for a TG-Code and returns the data."""

    if not os.path.exists(DATABASE_PATH):
        print(f"Error: Database file '{DATABASE_PATH}' not found.")
        print("Please run the import.py script first.")
        return None, None

    conn = None # Initialize conn to None
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        # Use Row factory to access columns by name
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # --- Build the Query Dynamically ---
        select_parts = ["e.*"] # Start with all columns from Emissionen table (aliased as 'e')
        join_parts = []
        normalized_mapping = {} # Map original name -> (table_name, id_col, alias)

        # Prepare joins for normalized columns
        for i, original_col in enumerate(NORMALIZE_COLUMNS_ORIGINAL):
            clean_base = clean_sql_identifier(original_col)
            if not clean_base: continue # Skip if cleaning results in empty string

            table_name = create_normalized_table_name(clean_base)
            # Ensure table_name was created successfully
            if not table_name:
                print(f"Warning: Could not generate table name for '{original_col}'")
                continue

            id_col_in_emissionen = f"{clean_base}_id"
            table_alias = f"t{i}" # Simple alias like t0, t1, etc.
            name_alias = original_col # Use original name as the alias for the joined name

            # Add the SELECT part for the normalized name
            # Use original_col for the alias as it's what the user expects to see
            select_parts.append(f"{table_alias}.name AS \"{name_alias}\"")

            # Add the LEFT JOIN part
            # Ensure id_col_in_emissionen is quoted if it might contain special chars (unlikely here)
            join_parts.append(
                f"LEFT JOIN {table_name} {table_alias} ON e.\"{id_col_in_emissionen}\" = {table_alias}.id"
            )
            # Store mapping using original_col as key for easier lookup in display function
            normalized_mapping[original_col] = (table_name, id_col_in_emissionen, name_alias)


        # Construct the final query
        query = f"""
            SELECT
                {', '.join(select_parts)}
            FROM
                Emissionen e
            {' '.join(join_parts)}
            WHERE
                e.TG_Code = ?
        """

        # Use the cleaned TG_Code for the WHERE clause as well
        cleaned_tg_code_col_name = clean_sql_identifier("TG-Code")
        query = query.replace("e.TG_Code = ?", f"e.{cleaned_tg_code_col_name} = ?")


        cursor.execute(query, (tg_code_to_search,))
        result = cursor.fetchone() # Fetch one row (TG_Code should be unique)

        if result:
            return result, normalized_mapping
        else:
            return None, None

    except sqlite3.Error as e:
        # Provide more specific error info if possible
        print(f"Database error during search: {e}")
        # It might be helpful to see the exact query causing the error
        # print(f"Query attempted:\n{query}")
        return None, None
    except Exception as e:
        print(f"An unexpected error occurred during search: {e}")
        return None, None
    finally:
        if conn:
            conn.close()

# --- Display Function (MODIFIED for Custom Order and Dividers) ---

def display_result(result_row, normalized_mapping):
    """Formats and prints the result row according to DISPLAY_ORDER_WITH_DIVIDERS."""
    print("-" * 40)
    # *** MODIFIED: Use TG_Code (underscore) to access the key ***
    print(f"Details for TG-Code: {result_row['TG_Code']} - {result_row['Marke']} - {result_row['Typ']}") # Use underscore
    print("-" * 40)

    # Get all available column names from the result row for checking existence
    available_columns = result_row.keys()

    # Iterate through the predefined display order
    for item_name in DISPLAY_ORDER_WITH_DIVIDERS:

        # Check for divider marker
        if item_name == DIVIDER_MARKER:
            print(DIVIDER_MARKER) # Print an empty line
            continue

        # If not a divider, treat as a column name
        col_name = item_name

        # --- Skip if column is TG_Code (already printed) ---
        # *** MODIFIED: Check for TG_Code (underscore) ***
        if col_name == 'TG_Code': # Use underscore
            continue

        # --- Skip if column doesn't exist in the result row ---
        # Use the name from the display list for checking existence in the result keys
        if col_name not in available_columns:
             # Check if the *cleaned* version exists (in case display list uses original but result has cleaned)
             cleaned_col_name_check = clean_sql_identifier(col_name)
             if cleaned_col_name_check not in available_columns:
                 # Optional: Print a warning if a defined column is missing from results
                 # print(f"Warning: Column '{col_name}' (or '{cleaned_col_name_check}') not found in result set.")
                 continue
             else:
                 # If cleaned name exists, use that to fetch value, but keep original display name
                 value = result_row[cleaned_col_name_check]
                 display_name = col_name # Keep original name for display
         # If original name exists, fetch using that
        else:
            value = result_row[col_name]
            display_name = col_name # Use the name from the display order list


        # --- Check if the column should be omitted based on the OMIT list ---
        # Clean the name *before* checking against the cleaned omit list
        cleaned_col_name_for_check = clean_sql_identifier(col_name)
        if cleaned_col_name_for_check in OMIT_COLUMNS_CLEANED:
            continue # Skip this column entirely

        # --- Process and format the value ---
        # value = result_row[col_name] # Value fetched above based on existence check
        display_value = "" # Default to empty string

        # 1. Handle Special Formatting (Date)
        # Use cleaned name for the check
        if clean_sql_identifier(col_name) == 'Homologationsdatum':
            if value:
                try:
                    date_obj = datetime.strptime(str(value), HOMOLOGATIONSDATUM_INPUT_FORMAT)
                    display_value = date_obj.strftime(HOMOLOGATIONSDATUM_OUTPUT_FORMAT)
                except (ValueError, TypeError):
                    display_value = f"{value} (format?)"
            # display_value remains "" if value was None/empty

        # 2. Handle '(leer)' placeholder for normalized fields
        # Check the actual value retrieved from the row
        elif isinstance(value, str) and value == '(leer)':
            display_value = ""

        # 3. Handle other non-None values
        elif value is not None:
             display_value = str(value)

        # 4. Add Units if applicable and value is not empty
        # Use cleaned name for the UNITS_MAP lookup
        cleaned_col_name_for_units = clean_sql_identifier(col_name)
        if display_value and cleaned_col_name_for_units in UNITS_MAP:
            display_value = f"{display_value} {UNITS_MAP[cleaned_col_name_for_units]}"

        # Print the final result for this column
        print(f"{display_name:<25}: {display_value}")

    print("-" * 40)


# --- Main Execution ---

if __name__ == "__main__":
    # Correction in OMIT_COLUMNS_ORIGINAL list (missing comma)
    # Ensure the list is correctly defined before creating the set
    OMIT_COLUMNS_ORIGINAL = [
        "ET_CO", "ET_NMHC", "ET_NOx", "ET_PA", "ET_PA_Exp", "ET_PM",
        "ET_THC", "ET_THC_NOx", "ET_T_IV_THC", "ET_T_VI_CO", "ET_T_VI_THC",
        "ScCo2", "ScConsumption", "ScNh3", "ScNo2", "TC_CO2", "TC_Consumption",
        "TC_NH3", "TC_NO2", "ZT_CO", "ZT_NMHC", "ZT_NOx", "ZT_PA", "ZT_PA_Exp", # Added comma here
        "ZT_PM", "ZT_THC", "ZT_THC_NOx", "ZT_T_IV_THC", "ZT_T_VI_CO", "ZT_T_VI_THC",
        "ZT_NMHC", "ZT_NOx", "ZT_AbgasCode"
    ]
    OMIT_COLUMNS_CLEANED = set(clean_sql_identifier(col) for col in OMIT_COLUMNS_ORIGINAL)


    if len(sys.argv) != 2:
        print("Usage: python search.py <TG-Code>")
        sys.exit(1)

    tg_code_input = sys.argv[1]

    print(f"Searching for TG-Code: {tg_code_input}...")
    data_row, norm_map = search_by_tg_code(tg_code_input)

    if data_row:
        display_result(data_row, norm_map)
    else:
        print(f"No data found for TG-Code '{tg_code_input}'.")

