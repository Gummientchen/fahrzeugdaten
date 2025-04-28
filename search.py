# search.py
import sqlite3
import sys
import os
import re
from datetime import datetime # Import datetime module
from fpdf.enums import XPos, YPos # Keep for potential future use if needed

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
    "Leergewicht_von": "kg", "Leergewicht_bis": "kg", "Garantiegewicht_von": "kg",
    "Garantiegewicht_bis": "kg", "Gesamtzuggewicht_bis": "kg", "Gesamtzuggewicht_von": "kg",
    "Vmax_von": "km/h", "Vmax_bis": "km/h", "Hubraum": "ccm", "Leistung": "kW",
    "Leistung_bei_n_min": "rpm", "Drehmoment": "Nm", "Drehmoment_bei_n_min": "rpm",
    "Fahrgeräusch": "dbA", "Standgeräusch": "dbA", "Standgeräusch_bei_n_min": "rpm"
}

# Conversion factor
KW_TO_PS = 1.35962

# Assumed input format for Homologationsdatum (e.g., YYYYMMDD)
# Adjust this if your data uses a different format
HOMOLOGATIONSDATUM_INPUT_FORMAT = '%Y%m%d'
# Desired output format (e.g., DD.MM.YYYY)
HOMOLOGATIONSDATUM_OUTPUT_FORMAT = '%d.%m.%Y'

# --- Columns to Omit from Output ---
OMIT_COLUMNS_ORIGINAL = [
    "ET_CO", "ET_NMHC", "ET_NOx", "ET_PA", "ET_PA_Exp", "ET_PM",
    "ET_THC", "ET_THC_NOx", "ET_T_IV_THC", "ET_T_VI_CO", "ET_T_VI_THC",
    "ScCo2", "ScConsumption", "ScNh3", "ScNo2", "TC_CO2", "TC_Consumption",
    "TC_NH3", "TC_NO2", "ZT_CO", "ZT_NMHC", "ZT_NOx", "ZT_PA", "ZT_PA_Exp",
    "ZT_PM", "ZT_THC", "ZT_THC_NOx", "ZT_T_IV_THC", "ZT_T_VI_CO", "ZT_T_VI_THC",
    "ZT_NMHC", "ZT_NOx", "ZT_AbgasCode"
]

# --- Desired Display Order with Dividers ---
DIVIDER_MARKER = "---"
DISPLAY_ORDER_WITH_DIVIDERS = [
    "TG_Code", "Marke", "Typ", "Homologationsdatum", "Antrieb", "Hubraum", "Treibstoff",
    DIVIDER_MARKER,
    "Drehmoment", "Drehmoment_bei_n_min", "Leistung", "Leistung_bei_n_min",
    DIVIDER_MARKER,
    "Leergewicht_bis", "Leergewicht_von", "Garantiegewicht_von",
    DIVIDER_MARKER,
    "Vmax_bis", "Vmax_von",
    DIVIDER_MARKER,
    "Fahrgeräusch", "Standgeräusch", "Standgeräusch_bei_n_min", "GeräuschCode",
    DIVIDER_MARKER,
    "Anz_Zylinder", "Getriebe", "Motormarke", "Motortyp", "Takte", "iAchse",
    "AbgasCode", "Abgasreinigung", "Anzahl_Achsen_Räder", "Bauart", "Bemerkung",
    "Emissionscode", "Garantiegewicht_bis", "Gesamtzuggewicht_bis", "Gesamtzuggewicht_von"
]

# --- NEW: Translation Dictionaries ---
ANTRIEB_MAP = {
    'V': 'Vorne',
    'A': 'Allrad',
    'H': 'Hinten'
}

TREIBSTOFF_MAP = {
    'D': 'Diesel',
    'B': 'Benzin',
    'E': 'Elektrisch'
}


# --- Helper Functions ---

def clean_sql_identifier(name):
    """Cleans a string to be a valid SQL identifier (table/column name)."""
    if not isinstance(name, str): return ""
    name = re.sub(r'[ /.\-+()]+', '_', name)
    name = name.replace('ET_THC_NOx', 'ET_THC_NOx')
    name = name.replace('ZT_THC_NOx', 'ZT_THC_NOx')
    name = name.strip('_')
    if name and name[0].isdigit(): name = '_' + name
    return name

# Create a set of cleaned names for faster lookup for omitting columns
OMIT_COLUMNS_CLEANED = set(clean_sql_identifier(col) for col in OMIT_COLUMNS_ORIGINAL)

def create_normalized_table_name(base_name):
    """Creates a pluralized table name for normalized columns."""
    clean_name = clean_sql_identifier(base_name)
    if not clean_name: return None
    if clean_name.endswith('e'): return f"{clean_name}n"
    elif clean_name.endswith('s'): return f"{clean_name}es"
    else: return f"{clean_name}s"

# --- Main Search Function ---
def search_by_tg_code(tg_code_to_search):
    """Searches the database for a TG-Code and returns the data."""
    if not os.path.exists(DATABASE_PATH):
        print(f"Error: Database file '{DATABASE_PATH}' not found.")
        return None, None
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        select_parts = ["e.*"]
        join_parts = []
        normalized_mapping = {}
        for i, original_col in enumerate(NORMALIZE_COLUMNS_ORIGINAL):
            clean_base = clean_sql_identifier(original_col)
            if not clean_base: continue
            table_name = create_normalized_table_name(clean_base)
            if not table_name: continue
            id_col_in_emissionen = f"{clean_base}_id"
            table_alias = f"t{i}"
            name_alias = original_col
            select_parts.append(f"{table_alias}.name AS \"{name_alias}\"")
            join_parts.append(
                f"LEFT JOIN {table_name} {table_alias} ON e.\"{id_col_in_emissionen}\" = {table_alias}.id"
            )
            normalized_mapping[original_col] = (table_name, id_col_in_emissionen, name_alias)
        query = f"""
            SELECT {', '.join(select_parts)}
            FROM Emissionen e {' '.join(join_parts)}
            WHERE e.TG_Code = ?
        """
        cleaned_tg_code_col_name = clean_sql_identifier("TG-Code")
        query = query.replace("e.TG_Code = ?", f"e.{cleaned_tg_code_col_name} = ?")
        cursor.execute(query, (tg_code_to_search,))
        result = cursor.fetchone()
        return (result, normalized_mapping) if result else (None, None)
    except sqlite3.Error as e:
        print(f"Database error during search: {e}")
        return None, None
    except Exception as e:
        print(f"An unexpected error occurred during search: {e}")
        return None, None
    finally:
        if conn: conn.close()


# --- Display Function (MODIFIED for Translations) ---

def display_result(result_row, normalized_mapping):
    """Formats and prints the result row according to DISPLAY_ORDER_WITH_DIVIDERS."""
    print("-" * 40)
    # Display TG_Code, Marke, Typ in the header
    print(f"Details for TG-Code: {result_row['TG_Code']} - {result_row['Marke']} - {result_row['Typ']}")
    print("-" * 40)

    # Get all available column names from the result row for checking existence
    available_columns = result_row.keys()

    # Iterate through the predefined display order
    for item_name in DISPLAY_ORDER_WITH_DIVIDERS:

        # Check for divider marker
        if item_name == DIVIDER_MARKER:
            print(DIVIDER_MARKER) # Print the marker string itself
            continue

        # If not a divider, treat as a column name
        col_name = item_name

        # --- Skip columns already printed in header ---
        if col_name in ['TG_Code', 'Marke', 'Typ']:
            continue

        # --- Skip if column doesn't exist in the result row ---
        value = None # Initialize value
        display_name = col_name # Default display name

        if col_name not in available_columns:
             # Check if the *cleaned* version exists
             cleaned_col_name_check = clean_sql_identifier(col_name)
             if cleaned_col_name_check not in available_columns:
                 continue # Skip if neither original nor cleaned name exists
             else:
                 # Use cleaned name to fetch value, keep original display name
                 value = result_row[cleaned_col_name_check]
        else:
            # Use original name to fetch value
            value = result_row[col_name]


        # --- Check if the column should be omitted based on the OMIT list ---
        cleaned_col_name_for_check = clean_sql_identifier(col_name)
        if cleaned_col_name_for_check in OMIT_COLUMNS_CLEANED:
            continue # Skip this column entirely

        # --- Process and format the value ---
        display_value = "" # Default to empty string
        is_leistung = (cleaned_col_name_for_check == 'Leistung')
        is_antrieb = (cleaned_col_name_for_check == 'Antrieb')
        is_treibstoff = (cleaned_col_name_for_check == 'Treibstoff')

        # 1. Handle Special Formatting (Date)
        if cleaned_col_name_for_check == 'Homologationsdatum':
            if value:
                try:
                    date_obj = datetime.strptime(str(value), HOMOLOGATIONSDATUM_INPUT_FORMAT)
                    display_value = date_obj.strftime(HOMOLOGATIONSDATUM_OUTPUT_FORMAT)
                except (ValueError, TypeError):
                    display_value = f"{value} (format?)"

        # 2. Handle '(leer)' placeholder for normalized fields
        elif isinstance(value, str) and value == '(leer)':
            display_value = ""

        # 3. Handle other non-None values (initial assignment)
        elif value is not None:
             display_value = str(value) # Convert to string for consistent handling

        # --- 4. Apply Translations (Antrieb, Treibstoff) ---
        # This happens *after* getting the raw value but *before* adding units/PS
        if is_antrieb and display_value:
            # Use .get() for safe lookup with fallback to original value
            display_value = ANTRIEB_MAP.get(display_value, display_value)
        elif is_treibstoff and display_value:
            # Use .get() for safe lookup with fallback to original value
            display_value = TREIBSTOFF_MAP.get(display_value, display_value)

        # --- 5. Add Units / Calculate PS ---
        cleaned_col_name_for_units = cleaned_col_name_for_check # Already have cleaned name

        # Special handling for Leistung (kW and PS)
        if is_leistung and display_value:
            try:
                # Extract only the numeric part if combined value exists (unlikely here, but safer)
                kw_str = display_value.split(' ')[0]
                kw_value_float = float(kw_str)
                ps_value = kw_value_float * KW_TO_PS
                ps_value_formatted = f"{ps_value:.1f}"
                # Combine kW and PS
                display_value = f"{kw_str} kW / {ps_value_formatted} PS"
            except ValueError:
                # If conversion to float fails, just add kW unit
                display_value = f"{display_value} kW (Invalid number for PS calc)"

        # Add units for other columns (if not Leistung and unit exists)
        elif display_value and cleaned_col_name_for_units in UNITS_MAP and not is_leistung:
            display_value = f"{display_value} {UNITS_MAP[cleaned_col_name_for_units]}"

        # Print the final result for this column
        print(f"{display_name:<25}: {display_value}")

    print("-" * 40)


# --- Main Execution ---

if __name__ == "__main__":
    # Ensure OMIT_COLUMNS_CLEANED is generated correctly
    OMIT_COLUMNS_ORIGINAL = [
        "ET_CO", "ET_NMHC", "ET_NOx", "ET_PA", "ET_PA_Exp", "ET_PM",
        "ET_THC", "ET_THC_NOx", "ET_T_IV_THC", "ET_T_VI_CO", "ET_T_VI_THC",
        "ScCo2", "ScConsumption", "ScNh3", "ScNo2", "TC_CO2", "TC_Consumption",
        "TC_NH3", "TC_NO2", "ZT_CO", "ZT_NMHC", "ZT_NOx", "ZT_PA", "ZT_PA_Exp",
        "ZT_PM", "ZT_THC", "ZT_THC_NOx", "ZT_T_IV_THC", "ZT_T_VI_CO", "ZT_T_VI_THC",
        "ZT_NMHC", "ZT_NOx", "ZT_AbgasCode"
    ]
    OMIT_COLUMNS_CLEANED = set(clean_sql_identifier(col) for col in OMIT_COLUMNS_ORIGINAL)


    if len(sys.argv) != 2:
        print("Usage: python search.py <TG-Code>")
        sys.exit(1)

    tg_code_input = sys.argv[1]

    print(f"Searching for TG-Code: {tg_code_input}...")
    # Use the imported search_by_tg_code function
    data_row, norm_map = search_by_tg_code(tg_code_input)

    if data_row:
        display_result(data_row, norm_map)
    else:
        print(f"No data found for TG-Code '{tg_code_input}'.")

