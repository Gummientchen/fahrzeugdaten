# search.py (CLI Interface)
import sys
import os

# Import refactored components
import config
import database
import formatting
from utils import clean_sql_identifier # Needed for checking header keys

def display_formatted_data_cli(formatted_data):
    """Prints formatted data to the console based on DISPLAY_ORDER."""
    if not formatted_data:
        print("No data to display.")
        return

    print("-" * 40)
    # --- Header ---
    # Safely get header values using original names
    tg_code_val = formatted_data.get('TG_Code', 'N/A')
    marke_val = formatted_data.get('Marke', 'N/A')
    typ_val = formatted_data.get('Typ', 'N/A')
    print(f"Details for TG-Code: {tg_code_val} - {marke_val} - {typ_val}")
    print("-" * 40)

    # --- Body ---
    for item_name in config.DISPLAY_ORDER_WITH_DIVIDERS:
        if item_name == config.DIVIDER_MARKER:
            print(config.DIVIDER_MARKER)
            continue

        # Skip header items already printed
        if item_name in ['TG_Code', 'Marke', 'Typ']:
            continue

        # Get the formatted value using the original item name as the key
        display_value = formatted_data.get(item_name, "") # Default to empty string if somehow missing

        # Print label (original name) and formatted value
        print(f"{item_name:<25}: {display_value}")

    print("-" * 40)


# --- Main Execution (CLI) ---
if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: python {os.path.basename(__file__)} <TG-Code>")
        sys.exit(1)

    tg_code_input = sys.argv[1]

    print(f"Searching for TG-Code: {tg_code_input}...")

    # 1. Search the database (gets raw data)
    raw_data_row = database.search_by_tg_code(tg_code_input)

    if raw_data_row:
        print("Data found. Formatting...")
        # 2. Format the raw data for display
        formatted_vehicle_data = formatting.format_vehicle_data(raw_data_row)
        # 3. Display the formatted data
        display_formatted_data_cli(formatted_vehicle_data)
    else:
        print(f"No data found for TG-Code '{tg_code_input}'.")

