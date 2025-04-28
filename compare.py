# compare.py
import argparse
import os
import datetime
from fpdf import FPDF
from fpdf.enums import XPos, YPos

# Import refactored components
import config
import database
import formatting
import translation # Import the new translation module
from utils import clean_sql_identifier, get_resource_path

# --- Data Fetching & Formatting for Comparison ---
def get_formatted_car_data_for_compare(tg_code):
    """Fetches raw data and returns formatted data for a single car."""
    raw_data = database.search_by_tg_code(tg_code)
    if not raw_data:
        return None
    # formatting.py now handles value translations
    return formatting.format_vehicle_data(raw_data)

# --- PDF Generation Class (Specific to Comparison) ---
class PDFCompare(FPDF):
    def header(self):
        # Set font (use the default family set during PDF creation)
        self.set_font(style='I', size=8)
        page_w = self.w - self.l_margin - self.r_margin
        # Header Text (Left Aligned) - Use translated title
        self.cell(page_w / 2, 10, translation._("pdf_title_compare"), border=0, align='L')
        # Date (Right Aligned) - Use translated "Generated:"
        generation_date = datetime.datetime.now().strftime("%d.%m.%Y")
        generated_text = translation._("pdf_generated_on")
        self.cell(page_w / 2, 10, f"{generated_text} {generation_date}", border=0, align='R', new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        # Line break and separator line
        self.ln(2)
        self.set_draw_color(180, 180, 180)
        self.set_line_width(config.PDF_DIVIDER_THICKNESS)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(5) # Space after header line

    def add_comparison_table(self, tg_codes, formatted_car_data_list):
        """Adds the main comparison table to the PDF using formatted data."""
        if not formatted_car_data_list or all(d is None for d in formatted_car_data_list):
            self.set_font_size(10)
            # Use translated message
            self.cell(0, 10, translation._("pdf_no_compare_data"), border=0, align='C', new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            return

        num_cars = len(formatted_car_data_list)
        if num_cars == 0: return

        # Calculate column widths
        page_width = self.w - 2 * self.l_margin
        label_col_width = page_width * 0.30
        data_col_width = (page_width - label_col_width) / num_cars

        # Table Styling
        self.set_draw_color(180, 180, 180) # Light Gray borders
        line_height = config.PDF_LINE_HEIGHT # Use configured line height

        # --- Header Row (TG-Codes) ---
        self.set_font(self.font_family, size=10, style='B') # Use self.font_family
        self.set_fill_color(230, 230, 230) # Light gray background for header
        # Empty cell for the label column header
        self.cell(label_col_width, line_height + 1, '', border=1, align='L', fill=True, new_x=XPos.RIGHT, new_y=YPos.TOP)
        # TG-Code cells - Translate "TG:" prefix
        tg_prefix = translation._("pdf_compare_tg_prefix")
        for i, tg_code in enumerate(tg_codes):
            is_last_cell = (i == num_cars - 1)
            next_x = XPos.LMARGIN if is_last_cell else XPos.RIGHT
            next_y = YPos.NEXT if is_last_cell else YPos.TOP
            self.cell(data_col_width, line_height + 1, f"{tg_prefix} {tg_code}", border=1, align='C', fill=True, new_x=next_x, new_y=next_y)

        # --- Data Rows ---
        self.set_font(self.font_family, size=8, style='') # Use self.font_family
        fill = False # Alternating row background color flag
        for field in config.DISPLAY_ORDER_WITH_DIVIDERS:
            if field == config.DIVIDER_MARKER:
                # Draw divider line across the table width
                self.ln(config.PDF_DIVIDER_MARGIN / 2)
                self.set_draw_color(180, 180, 180)
                self.set_line_width(config.PDF_DIVIDER_THICKNESS)
                self.line(self.l_margin, self.get_y(), self.l_margin + page_width, self.get_y())
                self.ln(config.PDF_DIVIDER_MARGIN / 2)
                continue

            # Skip header fields
            if field in ['TG_Code', 'Marke', 'Typ']:
                 continue

            # Label Cell (Bold) - Translate the field name
            self.set_font(self.font_family, size=8, style='B') # Use self.font_family
            self.set_fill_color(245, 245, 245) if fill else self.set_fill_color(255, 255, 255)
            start_y = self.get_y()
            translated_label = translation._(field) # Translate the label
            self.multi_cell(label_col_width, line_height, f" {translated_label}",
                            border=1, align='L', fill=True, new_x=XPos.RIGHT, new_y=YPos.TOP)
            label_end_y = self.get_y()

            # Value Cells for each car (Regular font)
            self.set_font(self.font_family, size=8, style='') # Use self.font_family
            max_y_in_row = start_y
            current_x = self.l_margin + label_col_width

            for i, car_data in enumerate(formatted_car_data_list):
                # Get the pre-formatted value (already translated by formatting.py if applicable)
                value = car_data.get(field, 'N/A') if car_data else 'N/A'
                self.set_xy(current_x, start_y)
                self.multi_cell(data_col_width, line_height, f" {value}",
                                border=1, align='L', fill=True)
                max_y_in_row = max(max_y_in_row, self.get_y())
                current_x += data_col_width

            self.set_y(max_y_in_row)
            fill = not fill


# --- Main Comparison PDF Generation Function ---
def generate_comparison_pdf(tg_codes, formatted_car_data_list):
    """Generates the comparison PDF using pre-formatted data."""
    if not formatted_car_data_list or all(d is None for d in formatted_car_data_list):
        print("Error: No valid formatted data found for any provided TG-Code.")
        return None

    try:
        # Ensure export directory exists
        os.makedirs(config.EXPORT_DIR_COMPARE, exist_ok=True)

        pdf = PDFCompare()
        # --- Font Handling ---
        font_family_to_use = config.PDF_FONT_FALLBACK # Start with fallback
        try:
            # Use paths from config
            font_path = get_resource_path(config.FONT_REGULAR_PATH)
            bold_font_path = get_resource_path(config.FONT_BOLD_PATH)
            italic_font_path = get_resource_path(config.FONT_ITALIC_PATH)
            bold_italic_font_path = get_resource_path(config.FONT_BOLD_ITALIC_PATH)

            # Check if all required font files exist
            if all(os.path.exists(p) for p in [font_path, bold_font_path, italic_font_path, bold_italic_font_path]):
                pdf.add_font(config.PDF_FONT_NAME_DEJAVU, '', font_path)
                pdf.add_font(config.PDF_FONT_NAME_DEJAVU, 'B', bold_font_path)
                pdf.add_font(config.PDF_FONT_NAME_DEJAVU, 'I', italic_font_path)
                pdf.add_font(config.PDF_FONT_NAME_DEJAVU, 'BI', bold_italic_font_path)
                font_family_to_use = config.PDF_FONT_NAME_DEJAVU # Switch to DejaVu
                print("Using DejaVu font for PDF.")
            else:
                 print(f"Warning: One or more DejaVu font files not found in '{config.FONT_DIR}'. Using fallback {font_family_to_use}.")
        except Exception as font_err:
            print(f"Warning: Failed to load DejaVu font ({font_err}). Using fallback {font_family_to_use}.")

        # Set the chosen font family
        pdf.set_font(font_family_to_use, '', 10) # Set default size


        pdf.add_page()
        pdf.set_margins(left=10, top=15, right=10) # Slightly smaller margins for table
        pdf.set_auto_page_break(auto=True, margin=15)

        # Add the comparison table content
        pdf.add_comparison_table(tg_codes, formatted_car_data_list)

        # --- Filename and Saving ---
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_tg_codes = [clean_sql_identifier(code).lstrip('_') for code in tg_codes]
        tg_codes_str = "_vs_".join(safe_tg_codes)
        filename = f"vergleich_{tg_codes_str}_{timestamp}.pdf"
        output_path = os.path.join(config.EXPORT_DIR_COMPARE, filename)

        pdf.output(output_path)
        return output_path # Return the full path of the generated PDF

    except ImportError:
         print("Error: FPDF library not found. Please install it using: pip install fpdf2")
         return None
    except OSError as e:
         print(f"Error creating directory or writing PDF file: {e}")
         return None
    except Exception as e:
        print(f"An error occurred during comparison PDF generation: {e}")
        import traceback
        traceback.print_exc()
        return None


# --- Main Execution (CLI) ---
# (CLI part remains unchanged, uses the updated generate_comparison_pdf)
def main():
    parser = argparse.ArgumentParser(description="Vergleicht 2 oder 3 Fahrzeuge anhand ihrer TG-Codes und exportiert das Ergebnis als PDF.")
    parser.add_argument('tg_codes', metavar='TG-CODE', nargs='+',
                        help='Zwei oder drei TG-Codes der zu vergleichenden Fahrzeuge.')

    args = parser.parse_args()
    tg_codes_input = args.tg_codes

    if not (2 <= len(tg_codes_input) <= 3):
        parser.error("Bitte geben Sie genau 2 oder 3 TG-Codes an.")

    print(f"Vergleiche Fahrzeuge mit TG-Codes: {', '.join(tg_codes_input)}")

    all_formatted_data = []
    valid_codes_found = []

    # Initialize translations for CLI run (using default language)
    translation.initialize_translations()

    for tg_code in tg_codes_input:
        print(f"Suche und formatiere Daten für TG-Code: {tg_code}...")
        formatted_data = get_formatted_car_data_for_compare(tg_code)
        if formatted_data:
            print(f" -> Daten für {tg_code} gefunden und formatiert.")
            all_formatted_data.append(formatted_data)
            valid_codes_found.append(tg_code) # Keep track of codes actually used
        else:
            print(f" -> Warnung: Keine Daten für TG-Code {tg_code} gefunden.")
            all_formatted_data.append(None) # Add placeholder if data not found
            valid_codes_found.append(tg_code) # Still include code in header list

    if not any(all_formatted_data): # Check if at least one car had data
         print("\nFehler: Für keinen der angegebenen TG-Codes konnten Daten gefunden werden.")
         return

    # Generate PDF using the collected formatted data
    pdf_path = generate_comparison_pdf(valid_codes_found, all_formatted_data)

    if pdf_path:
        print(f"\nVergleichs-PDF erfolgreich erstellt: {pdf_path}")
    else:
        print("\nFehler beim Erstellen des Vergleichs-PDFs.")

if __name__ == "__main__":
    main()
