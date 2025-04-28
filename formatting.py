# formatting.py
from datetime import datetime
import config
from utils import clean_sql_identifier
import translation # Import the new translation module

def format_vehicle_data(result_row):
    """
    Takes a raw database row (sqlite3.Row or dict) and returns a dictionary
    with values formatted for display (strings).
    Applies date formatting, unit suffixes, PS calculation, and translations.
    """
    if not result_row:
        return {}

    formatted_data = {}
    available_columns = result_row.keys() # Get column names from the Row object

    # Iterate through all available columns in the result row
    for original_col_name in available_columns:
        # Skip the normalized ID columns (e.g., Marke_id)
        if original_col_name.endswith("_id") and original_col_name[:-3] in [clean_sql_identifier(c) for c in config.NORMALIZE_COLUMNS]:
             continue

        cleaned_col_name = clean_sql_identifier(original_col_name)

        # Skip columns marked for omission
        if cleaned_col_name in config.OMIT_COLUMNS_CLEANED:
            continue

        value = result_row[original_col_name] # Access value using the original name from the Row object

        # --- Process and format the value ---
        display_value = "" # Default to empty string
        is_leistung = (cleaned_col_name == 'Leistung')
        is_antrieb = (cleaned_col_name == 'Antrieb')
        is_treibstoff = (cleaned_col_name == 'Treibstoff')

        # 1. Handle Special Formatting (Date)
        if cleaned_col_name == 'Homologationsdatum':
            if value:
                try:
                    # Input format might be YYYYMMDD as string from DB
                    date_obj = datetime.strptime(str(value), config.HOMOLOGATIONSDATUM_INPUT_FORMAT)
                    display_value = date_obj.strftime(config.HOMOLOGATIONSDATUM_OUTPUT_FORMAT)
                except (ValueError, TypeError):
                    display_value = f"{value} (format?)" # Fallback if parsing fails

        # 2. Handle '(leer)' placeholder (often comes from normalized tables)
        elif isinstance(value, str) and value == '(leer)':
            # Use translation for the placeholder itself
            display_value = translation._("(leer)") # Translate the placeholder

        # 3. Handle other non-None values (initial assignment)
        elif value is not None:
             display_value = str(value) # Convert to string for consistent handling

        # --- 4. Apply Translations (Antrieb, Treibstoff) using translation module ---
        # This happens *after* getting the raw value but *before* adding units/PS
        if is_antrieb and display_value in ['V', 'H', 'A']: # Check for valid keys
            # Construct the translation key, e.g., "antrieb_V"
            translation_key = f"antrieb_{display_value}"
            display_value = translation._(translation_key)
        elif is_treibstoff and display_value in ['D', 'B', 'E']: # Check for valid keys
            # Construct the translation key, e.g., "treibstoff_D"
            translation_key = f"treibstoff_{display_value}"
            display_value = translation._(translation_key)

        # --- 5. Add Units / Calculate PS ---
        # Special handling for Leistung (kW and PS)
        if is_leistung and display_value:
            try:
                # Extract numeric part, assuming it might have " kW / ... PS" already if formatted elsewhere (unlikely now)
                # Or just the raw number if coming directly from DB
                kw_str = display_value.split(' ')[0]
                kw_value_float = float(kw_str)
                ps_value = kw_value_float * config.KW_TO_PS
                ps_value_formatted = f"{ps_value:.1f}"
                # Use translation keys for "kW" and "PS" if desired, or keep simple
                display_value = f"{kw_str} kW / {ps_value_formatted} PS" # Combine kW and PS
            except (ValueError, TypeError):
                # If conversion fails, just add kW unit if possible
                display_value = f"{display_value} kW (Invalid)"

        # Add units for other columns (if value exists, unit is defined, and not Leistung)
        elif display_value and cleaned_col_name in config.UNITS_MAP and not is_leistung:
            display_value = f"{display_value} {config.UNITS_MAP[cleaned_col_name]}"

        # Store the final formatted string in the dictionary
        # Use the original column name as the key for consistency with DISPLAY_ORDER
        formatted_data[original_col_name] = display_value

    return formatted_data
