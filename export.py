# export_pdf.py
import sys
import os
# import re # No longer needed directly
from datetime import datetime
from fpdf import FPDF # Import the PDF library
from fpdf.enums import XPos, YPos # Import necessary enums for positioning

# --- Import shared elements from search.py ---
try:
    from search import (
        DATABASE_PATH, NORMALIZE_COLUMNS_ORIGINAL, UNITS_MAP, KW_TO_PS,
        HOMOLOGATIONSDATUM_INPUT_FORMAT, HOMOLOGATIONSDATUM_OUTPUT_FORMAT,
        OMIT_COLUMNS_ORIGINAL, OMIT_COLUMNS_CLEANED, # Import the derived set too
        DIVIDER_MARKER, DISPLAY_ORDER_WITH_DIVIDERS,
        clean_sql_identifier, # Import helper if needed by PDF generation logic directly
        # create_normalized_table_name, # Not directly needed by PDF generation
        search_by_tg_code # Import the main search function
    )
except ImportError:
    print("Error: Could not import from 'search.py'. Make sure it's in the same directory.")
    sys.exit(1)

# --- PDF Specific Configuration (Remains in this file) ---
PDF_TITLE = "Fahrzeugdatenblatt"
# *** MODIFIED: Use core font name directly ***
PDF_FONT = "Helvetica" # Changed from "Arial"
PDF_FONT_SIZE_TITLE = 16
PDF_FONT_SIZE_HEADER = 12
PDF_FONT_SIZE_BODY = 10
PDF_LABEL_WIDTH = 60 # Width for the label column in mm (Restored)
PDF_LINE_HEIGHT = 6 # Line height in mm (Restored)
PDF_DIVIDER_THICKNESS = 0.2 # Thickness of divider lines in mm
PDF_DIVIDER_MARGIN = 3 # Space above/below divider line in mm

# --- NEW: Export Directory Configuration ---
EXPORT_DIR = "export"


# --- PDF Generation Function (Restored Side-by-Side Layout with Fix & Deprecation Fixes) ---

def create_pdf(result_row, normalized_mapping, output_filename):
    """Creates a formatted PDF from the result row with side-by-side layout."""
    try:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_margins(left=15, top=15, right=15)
        pdf.set_auto_page_break(auto=True, margin=15)

        # --- Title ---
        pdf.set_font(PDF_FONT, 'B', PDF_FONT_SIZE_TITLE)
        # *** MODIFIED: Replace ln=True ***
        pdf.cell(0, 10, PDF_TITLE, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C')
        pdf.ln(5) # Space after title

        # --- Header (TG_Code, Marke, Typ) ---
        pdf.set_font(PDF_FONT, 'B', PDF_FONT_SIZE_HEADER)
        # Access result_row using keys from the database (TG_Code, Marke, Typ)
        header_text = f"{result_row['TG_Code']} - {result_row['Marke']} - {result_row['Typ']}"
        # *** MODIFIED: Replace ln=True ***
        pdf.cell(0, 8, header_text, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L')
        pdf.ln(8) # Space after header

        # --- Body Content ---
        available_columns = result_row.keys()
        # Calculate effective page width ONCE
        page_width = pdf.w - pdf.l_margin - pdf.r_margin
        # Calculate width available for the value cell ONCE
        value_width = page_width - PDF_LABEL_WIDTH

        # Check if calculated value width is valid
        if value_width <= 0:
             print("Error: Calculated width for value column is zero or negative. Check page margins and label width.")
             return # Stop PDF generation

        # Use DISPLAY_ORDER_WITH_DIVIDERS imported from search.py
        for item_name in DISPLAY_ORDER_WITH_DIVIDERS:
            # Handle Divider (use DIVIDER_MARKER from search.py)
            if item_name == DIVIDER_MARKER:
                pdf.ln(PDF_DIVIDER_MARGIN) # Space before line
                pdf.set_draw_color(180, 180, 180) # Light grey line
                pdf.set_line_width(PDF_DIVIDER_THICKNESS)
                # Ensure line starts at the left margin
                pdf.line(pdf.l_margin, pdf.get_y(), pdf.l_margin + page_width, pdf.get_y())
                pdf.ln(PDF_DIVIDER_MARGIN) # Space after line
                continue

            col_name = item_name

            # Skip header columns already printed
            if col_name in ['TG_Code', 'Marke', 'Typ']:
                continue

            # Check existence and get value
            value = None
            display_name = col_name
            if col_name not in available_columns:
                 # Use clean_sql_identifier imported from search.py
                 cleaned_col_name_check = clean_sql_identifier(col_name)
                 if cleaned_col_name_check not in available_columns:
                     continue
                 else:
                     value = result_row[cleaned_col_name_check]
            else:
                value = result_row[col_name]

            # Check if omitted (use OMIT_COLUMNS_CLEANED from search.py)
            cleaned_col_name_for_check = clean_sql_identifier(col_name)
            if cleaned_col_name_for_check in OMIT_COLUMNS_CLEANED:
                continue

            # Format the value (logic remains here, uses imported constants)
            display_value = ""
            is_leistung = (clean_sql_identifier(col_name) == 'Leistung')

            # Use HOMOLOGATIONSDATUM constants from search.py
            if clean_sql_identifier(col_name) == 'Homologationsdatum':
                if value:
                    try:
                        date_obj = datetime.strptime(str(value), HOMOLOGATIONSDATUM_INPUT_FORMAT)
                        display_value = date_obj.strftime(HOMOLOGATIONSDATUM_OUTPUT_FORMAT)
                    except (ValueError, TypeError): display_value = f"{value} (format?)"
            elif isinstance(value, str) and value == '(leer)': display_value = ""
            elif value is not None: display_value = str(value)

            # Add Units / Calculate PS (use KW_TO_PS and UNITS_MAP from search.py)
            cleaned_col_name_for_units = clean_sql_identifier(col_name)
            if is_leistung and display_value:
                try:
                    kw_value_float = float(display_value)
                    ps_value = kw_value_float * KW_TO_PS
                    ps_value_formatted = f"{ps_value:.1f}"
                    display_value = f"{display_value} kW / {ps_value_formatted} PS"
                except ValueError:
                    display_value = f"{display_value} kW (Invalid number)"
            elif display_value and cleaned_col_name_for_units in UNITS_MAP and not is_leistung:
                display_value = f"{display_value} {UNITS_MAP[cleaned_col_name_for_units]}"

            # --- Add Label and Value to PDF (Side-by-Side with Fix) ---

            # Explicitly set X position to left margin before drawing label
            pdf.set_x(pdf.l_margin)

            # Store Y position before drawing potentially multi-line cells
            start_y = pdf.get_y()

            # Draw Label Cell
            pdf.set_font(PDF_FONT, 'B', PDF_FONT_SIZE_BODY)
            # *** MODIFIED: Replace ln=3 ***
            pdf.multi_cell(PDF_LABEL_WIDTH, PDF_LINE_HEIGHT, f"{display_name}:", border=0, align='L', new_x=XPos.RIGHT, new_y=YPos.TOP)

            # Store Y position after drawing label (might have wrapped)
            label_end_y = pdf.get_y()

            # Reset Y position to start of line and move X for value cell
            pdf.set_xy(pdf.l_margin + PDF_LABEL_WIDTH, start_y)

            # Draw Value Cell
            pdf.set_font(PDF_FONT, '', PDF_FONT_SIZE_BODY)
            # *** MODIFIED: Replace ln=1 ***
            pdf.multi_cell(value_width, PDF_LINE_HEIGHT, display_value, border=0, align='L', new_x=XPos.LMARGIN, new_y=YPos.NEXT)

            # Store Y position after drawing value (might have wrapped)
            value_end_y = pdf.get_y()

            # Set Y position to the maximum height reached by either cell for consistent spacing
            # Make sure the new Y is at least start_y + line_height if no wrapping occurred
            new_y = max(label_end_y, value_end_y, start_y + PDF_LINE_HEIGHT)
            pdf.set_y(new_y)

            # Add a small gap if needed (optional, new_y handling might be enough)
            # pdf.ln(1)


        # --- Save the PDF ---
        pdf.output(output_filename)
        print(f"PDF exported successfully to '{output_filename}'")

    except ImportError:
         print("Error: FPDF library not found. Please install it using: pip install fpdf2")
    except Exception as e:
        print(f"An error occurred during PDF generation: {e}")


# --- Main Execution ---

if __name__ == "__main__":
    # No need to redefine OMIT_COLUMNS_CLEANED here, it's imported

    if len(sys.argv) != 2:
        print("Usage: python export_pdf.py <TG-Code>")
        sys.exit(1)

    tg_code_input = sys.argv[1]

    print(f"Searching for TG-Code: {tg_code_input}...")
    # Use the imported search_by_tg_code function
    data_row, norm_map = search_by_tg_code(tg_code_input)

    if data_row:
        # --- Create Export Directory and Construct Full Path ---
        try:
            os.makedirs(EXPORT_DIR, exist_ok=True)

            # Clean the input TG code for filename use
            cleaned_name_part = clean_sql_identifier(tg_code_input)
            # *** FIX: Remove leading underscore if present ***
            safe_filename_part = cleaned_name_part.lstrip('_')

            # Construct base filename using the safe part
            base_filename = f"{safe_filename_part}.pdf"
            # Construct the full path including the directory
            full_pdf_path = os.path.join(EXPORT_DIR, base_filename)

            print(f"Data found. Generating PDF: '{full_pdf_path}'...")
            # Pass the full path to the create_pdf function
            create_pdf(data_row, norm_map, full_pdf_path)

        except OSError as e:
            print(f"Error creating directory '{EXPORT_DIR}': {e}")
        except Exception as e:
            # Catch other potential errors during path construction or PDF call
             print(f"An error occurred before or during PDF generation: {e}")

    else:
        print(f"No data found for TG-Code '{tg_code_input}'.")

