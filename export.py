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
        search_by_tg_code, # Import the main search function
        # *** NEW: Import translation maps ***
        ANTRIEB_MAP, TREIBSTOFF_MAP
    )
except ImportError:
    print("Error: Could not import from 'search.py'. Make sure it's in the same directory.")
    sys.exit(1)

# --- PDF Specific Configuration (Remains in this file) ---
PDF_TITLE = "Fahrzeugdatenblatt"
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


# --- PDF Generation Function (MODIFIED for Translations) ---

def create_pdf(result_row, normalized_mapping, output_filename):
    """Creates a formatted PDF from the result row with side-by-side layout."""
    try:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_margins(left=15, top=15, right=15)
        pdf.set_auto_page_break(auto=True, margin=15)

        # --- Title ---
        pdf.set_font(PDF_FONT, 'B', PDF_FONT_SIZE_TITLE)
        pdf.cell(0, 10, PDF_TITLE, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C')
        pdf.ln(5) # Space after title

        # --- Header (TG_Code, Marke, Typ) ---
        pdf.set_font(PDF_FONT, 'B', PDF_FONT_SIZE_HEADER)
        header_text = f"{result_row['TG_Code']} - {result_row['Marke']} - {result_row['Typ']}"
        pdf.cell(0, 8, header_text, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L')
        pdf.ln(8) # Space after header

        # --- Body Content ---
        available_columns = result_row.keys()
        page_width = pdf.w - pdf.l_margin - pdf.r_margin
        value_width = page_width - PDF_LABEL_WIDTH

        if value_width <= 0:
             print("Error: Calculated width for value column is zero or negative.")
             return

        for item_name in DISPLAY_ORDER_WITH_DIVIDERS:
            if item_name == DIVIDER_MARKER:
                pdf.ln(PDF_DIVIDER_MARGIN)
                pdf.set_draw_color(180, 180, 180)
                pdf.set_line_width(PDF_DIVIDER_THICKNESS)
                pdf.line(pdf.l_margin, pdf.get_y(), pdf.l_margin + page_width, pdf.get_y())
                pdf.ln(PDF_DIVIDER_MARGIN)
                continue

            col_name = item_name

            if col_name in ['TG_Code', 'Marke', 'Typ']:
                continue

            value = None
            display_name = col_name
            if col_name not in available_columns:
                 cleaned_col_name_check = clean_sql_identifier(col_name)
                 if cleaned_col_name_check not in available_columns:
                     continue
                 else:
                     value = result_row[cleaned_col_name_check]
            else:
                value = result_row[col_name]

            cleaned_col_name_for_check = clean_sql_identifier(col_name)
            if cleaned_col_name_for_check in OMIT_COLUMNS_CLEANED:
                continue

            # Format the value
            display_value = ""
            is_leistung = (cleaned_col_name_for_check == 'Leistung')
            is_antrieb = (cleaned_col_name_for_check == 'Antrieb')
            is_treibstoff = (cleaned_col_name_for_check == 'Treibstoff')

            if cleaned_col_name_for_check == 'Homologationsdatum':
                if value:
                    try:
                        date_obj = datetime.strptime(str(value), HOMOLOGATIONSDATUM_INPUT_FORMAT)
                        display_value = date_obj.strftime(HOMOLOGATIONSDATUM_OUTPUT_FORMAT)
                    except (ValueError, TypeError): display_value = f"{value} (format?)"
            elif isinstance(value, str) and value == '(leer)': display_value = ""
            elif value is not None: display_value = str(value)

            # --- Apply Translations (Antrieb, Treibstoff) ---
            if is_antrieb and display_value:
                # Use imported ANTRIEB_MAP
                display_value = ANTRIEB_MAP.get(display_value, display_value)
            elif is_treibstoff and display_value:
                # Use imported TREIBSTOFF_MAP
                display_value = TREIBSTOFF_MAP.get(display_value, display_value)

            # --- Add Units / Calculate PS ---
            cleaned_col_name_for_units = cleaned_col_name_for_check

            if is_leistung and display_value:
                try:
                    kw_str = display_value.split(' ')[0]
                    kw_value_float = float(kw_str)
                    ps_value = kw_value_float * KW_TO_PS
                    ps_value_formatted = f"{ps_value:.1f}"
                    display_value = f"{kw_str} kW / {ps_value_formatted} PS"
                except ValueError:
                    display_value = f"{display_value} kW (Invalid number)"
            elif display_value and cleaned_col_name_for_units in UNITS_MAP and not is_leistung:
                display_value = f"{display_value} {UNITS_MAP[cleaned_col_name_for_units]}"

            # --- Add Label and Value to PDF ---
            pdf.set_x(pdf.l_margin)
            start_y = pdf.get_y()
            pdf.set_font(PDF_FONT, 'B', PDF_FONT_SIZE_BODY)
            pdf.multi_cell(PDF_LABEL_WIDTH, PDF_LINE_HEIGHT, f"{display_name}:", border=0, align='L', new_x=XPos.RIGHT, new_y=YPos.TOP)
            label_end_y = pdf.get_y()
            pdf.set_xy(pdf.l_margin + PDF_LABEL_WIDTH, start_y)
            pdf.set_font(PDF_FONT, '', PDF_FONT_SIZE_BODY)
            pdf.multi_cell(value_width, PDF_LINE_HEIGHT, display_value, border=0, align='L', new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            value_end_y = pdf.get_y()
            new_y = max(label_end_y, value_end_y, start_y + PDF_LINE_HEIGHT)
            pdf.set_y(new_y)

        # --- Save the PDF ---
        pdf.output(output_filename)
        print(f"PDF exported successfully to '{output_filename}'")

    except ImportError:
         print("Error: FPDF library not found. Please install it using: pip install fpdf2")
    except Exception as e:
        print(f"An error occurred during PDF generation: {e}")


# --- Main Execution ---

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python export_pdf.py <TG-Code>")
        sys.exit(1)

    tg_code_input = sys.argv[1]

    print(f"Searching for TG-Code: {tg_code_input}...")
    data_row, norm_map = search_by_tg_code(tg_code_input)

    if data_row:
        try:
            os.makedirs(EXPORT_DIR, exist_ok=True)
            cleaned_name_part = clean_sql_identifier(tg_code_input)
            safe_filename_part = cleaned_name_part.lstrip('_')
            base_filename = f"{safe_filename_part}.pdf"
            full_pdf_path = os.path.join(EXPORT_DIR, base_filename)
            print(f"Data found. Generating PDF: '{full_pdf_path}'...")
            create_pdf(data_row, norm_map, full_pdf_path)
        except OSError as e:
            print(f"Error creating directory '{EXPORT_DIR}': {e}")
        except Exception as e:
             print(f"An error occurred before or during PDF generation: {e}")
    else:
        print(f"No data found for TG-Code '{tg_code_input}'.")

