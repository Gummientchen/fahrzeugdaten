# c:\Users\steff\Documents\Github\fahrzeugdaten\compare.py

import argparse
import os
import datetime
from fpdf import FPDF
from fpdf.enums import XPos, YPos

# --- Define constants specific to this script ---
EXPORT_DIR = "export" # Define EXPORT_DIR here

# Import necessary functions and constants from search.py
try:
    from search import (
        search_by_tg_code,
        DATABASE_PATH, # Use the correct name from search.py
        DISPLAY_ORDER_WITH_DIVIDERS, # Use the correct name from search.py
        DIVIDER_MARKER, # Import the divider marker as well
    )
except ImportError as e: # Add 'as e' to see the specific error if needed
    print(f"Error importing from search.py: {e}")
    print("Make sure search.py is in the same directory and all imported names exist.")
    exit(1)
except Exception as e: # Catch other potential errors during import
     print(f"An unexpected error occurred during import: {e}")
     exit(1)


# --- Refined Data Fetching ---
# ... (get_formatted_car_data function remains the same) ...
def get_formatted_car_data(tg_code):
    """
    Fetches and formats car data using search.py logic.
    Returns a dictionary suitable for comparison.
    """
    result_row, _ = search_by_tg_code(tg_code) # Ignore normalized_mapping for now
    if not result_row:
        return None

    formatted_data = {}
    if result_row:
        from search import (
            UNITS_MAP, KW_TO_PS, HOMOLOGATIONSDATUM_INPUT_FORMAT,
            HOMOLOGATIONSDATUM_OUTPUT_FORMAT, ANTRIEB_MAP, TREIBSTOFF_MAP,
            OMIT_COLUMNS_CLEANED, clean_sql_identifier
        )
        available_columns = result_row.keys()
        for col_name in available_columns:
            cleaned_col_name_for_check = clean_sql_identifier(col_name)
            if cleaned_col_name_for_check in OMIT_COLUMNS_CLEANED:
                continue
            value = result_row[col_name]
            display_value = ""
            is_leistung = (cleaned_col_name_for_check == 'Leistung')
            is_antrieb = (cleaned_col_name_for_check == 'Antrieb')
            is_treibstoff = (cleaned_col_name_for_check == 'Treibstoff')
            if cleaned_col_name_for_check == 'Homologationsdatum':
                if value:
                    try:
                        date_obj = datetime.datetime.strptime(str(value), HOMOLOGATIONSDATUM_INPUT_FORMAT)
                        display_value = date_obj.strftime(HOMOLOGATIONSDATUM_OUTPUT_FORMAT)
                    except (ValueError, TypeError): display_value = f"{value} (format?)"
            elif isinstance(value, str) and value == '(leer)': display_value = ""
            elif value is not None: display_value = str(value)
            if is_antrieb and display_value:
                display_value = ANTRIEB_MAP.get(display_value, display_value)
            elif is_treibstoff and display_value:
                display_value = TREIBSTOFF_MAP.get(display_value, display_value)
            cleaned_col_name_for_units = cleaned_col_name_for_check
            if is_leistung and display_value:
                try:
                    kw_str = display_value.split(' ')[0]
                    kw_value_float = float(kw_str)
                    ps_value = kw_value_float * KW_TO_PS
                    ps_value_formatted = f"{ps_value:.1f}"
                    display_value = f"{kw_str} kW / {ps_value_formatted} PS"
                except (ValueError, TypeError):
                    display_value = f"{display_value} kW (Invalid)"
            elif display_value and cleaned_col_name_for_units in UNITS_MAP and not is_leistung:
                display_value = f"{display_value} {UNITS_MAP[cleaned_col_name_for_units]}"
            formatted_data[col_name] = display_value
    return formatted_data


# --- PDF Generation ---

class PDF(FPDF):
    # --- UPDATED HEADER METHOD ---
    def header(self):
        # This method is called automatically for each page
        # Set font (use the default family set during PDF creation)
        self.set_font(style='I', size=8) # Italic, small size
        # Get current page width
        page_w = self.w - self.l_margin - self.r_margin
        # Header Text (Left Aligned)
        header_title = "Fahrzeugvergleich"
        self.cell(page_w / 2, 10, header_title, border=0, align='L')
        # Date (Right Aligned)
        generation_date = datetime.datetime.now().strftime("%d.%m.%Y")
        self.cell(page_w / 2, 10, f"Generiert: {generation_date}", border=0, align='R', new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        # Line break and separator line
        self.ln(2) # Space before line
        self.set_draw_color(180, 180, 180) # Use same gray as table borders
        self.set_line_width(0.2)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        # Move down to leave space below header line
        self.ln(5) # Space after header line before main content starts

    # --- add_comparison_table method remains the same ---
    def add_comparison_table(self, tg_codes, car_data_list, display_order_with_dividers):
        """Adds the main comparison table to the PDF."""
        if not car_data_list:
            self.set_font_size(10)
            self.cell(0, 10, "Keine Daten zum Vergleichen vorhanden.", border=0, align='C', new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            return

        num_cars = len(car_data_list)
        if num_cars == 0: return

        page_width = self.w - 2 * self.l_margin
        label_col_width = page_width * 0.35
        data_col_width = (page_width - label_col_width) / num_cars

        self.set_draw_color(180, 180, 180) # Light Gray

        # --- Header Row (TG-Codes) ---
        self.set_font(size=10, style='B')
        self.set_fill_color(230, 230, 230)
        self.cell(label_col_width, 7, '', border=1, align='L', fill=True, new_x=XPos.RIGHT, new_y=YPos.TOP)
        for i, tg_code in enumerate(tg_codes):
            is_last_cell = (i == num_cars - 1)
            next_x = XPos.LMARGIN if is_last_cell else XPos.RIGHT
            next_y = YPos.NEXT if is_last_cell else YPos.TOP
            self.cell(data_col_width, 7, f"TG: {tg_code}", border=1, align='C', fill=True, new_x=next_x, new_y=next_y)

        # --- Data Rows ---
        self.set_font(size=8, style='')
        fill = False
        for field in display_order_with_dividers:
            if field == DIVIDER_MARKER:
                # Use the user-preferred spacing
                self.ln(2)
                self.set_draw_color(180, 180, 180)
                self.set_line_width(0.2)
                self.line(self.l_margin, self.get_y(), self.l_margin + page_width, self.get_y())
                self.ln(2)
                continue

            display_label = field.replace('_', ' ').title()
            max_h = 6

            # Label Cell
            self.set_font(size=8, style='B')
            self.set_fill_color(245, 245, 245) if fill else self.set_fill_color(255, 255, 255)
            self.cell(label_col_width, max_h, f" {display_label}", border=1, align='L', fill=fill, new_x=XPos.RIGHT, new_y=YPos.TOP)

            # Value Cells for each car
            self.set_font(size=8, style='')
            for i, car_data in enumerate(car_data_list):
                value = car_data.get(field, 'N/A') if car_data else 'N/A'
                is_last_cell = (i == num_cars - 1)
                next_x = XPos.LMARGIN if is_last_cell else XPos.RIGHT
                next_y = YPos.NEXT if is_last_cell else YPos.TOP
                self.cell(data_col_width, max_h, f" {value}", border=1, align='L', fill=fill, new_x=next_x, new_y=next_y)

            fill = not fill


# --- UPDATED PDF GENERATION FUNCTION ---
def generate_comparison_pdf(tg_codes, car_data_list, display_order_with_dividers, output_dir):
    """Generates the comparison PDF."""
    if not car_data_list or all(d is None for d in car_data_list):
        print("Error: No valid data found for any provided TG-Code.")
        return None

    os.makedirs(output_dir, exist_ok=True)

    pdf = PDF()
    # --- Font Handling ---
    try:
        pdf.add_font('DejaVu', '', 'DejaVuSans.ttf')
        pdf.add_font('DejaVu', 'B', 'DejaVuSans-Bold.ttf')
        pdf.add_font('DejaVu', 'I', 'DejaVuSans-Oblique.ttf')
        pdf.add_font('DejaVu', 'BI', 'DejaVuSans-BoldOblique.ttf')
        pdf.set_font('DejaVu', '', 10) # Set default font family
        # print("Using DejaVu font.") # Optional: Keep commented out
    except FileNotFoundError:
        pdf.set_font('Helvetica', '', 10) # Fallback default font family

    # --- Add Page (this automatically calls the header() method) ---
    pdf.add_page()

    # --- Add the comparison table ---
    # This will start below the header and the main title
    pdf.add_comparison_table(tg_codes, car_data_list, display_order_with_dividers)

    # --- Filename and Saving ---
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    tg_codes_str = "_".join(tg_codes)
    filename = f"vergleich_{tg_codes_str}_{timestamp}.pdf"
    output_path = os.path.join(output_dir, filename)

    try:
        pdf.output(output_path)
        return output_path
    except Exception as e:
        print(f"Error saving PDF: {e}")
        return None

# --- Main Execution ---
# ... (main function remains the same) ...
def main():
    parser = argparse.ArgumentParser(description="Vergleicht 2 oder 3 Fahrzeuge anhand ihrer TG-Codes und exportiert das Ergebnis als PDF.")
    parser.add_argument('tg_codes', metavar='TG-CODE', nargs='+',
                        help='Zwei oder drei TG-Codes der zu vergleichenden Fahrzeuge.')

    args = parser.parse_args()
    tg_codes_input = args.tg_codes

    if not (2 <= len(tg_codes_input) <= 3):
        parser.error("Bitte geben Sie genau 2 oder 3 TG-Codes an.")

    print(f"Vergleiche Fahrzeuge mit TG-Codes: {', '.join(tg_codes_input)}")

    all_car_data_formatted = []
    valid_tg_codes_for_header = []

    for tg_code in tg_codes_input:
        print(f"Suche und formatiere Daten für TG-Code: {tg_code}...")
        formatted_data = get_formatted_car_data(tg_code)
        if formatted_data:
            print(f" -> Daten für {tg_code} gefunden und formatiert.")
            all_car_data_formatted.append(formatted_data)
            valid_tg_codes_for_header.append(tg_code)
        else:
            print(f" -> Warnung: Keine Daten für TG-Code {tg_code} gefunden.")
            all_car_data_formatted.append(None)
            valid_tg_codes_for_header.append(tg_code)

    if not any(all_car_data_formatted):
         print("\nFehler: Für keinen der angegebenen TG-Codes konnten Daten gefunden werden.")
         return

    pdf_path = generate_comparison_pdf(
        valid_tg_codes_for_header,
        all_car_data_formatted,
        DISPLAY_ORDER_WITH_DIVIDERS,
        EXPORT_DIR
    )

    if pdf_path:
        print(f"\nVergleichs-PDF erfolgreich erstellt: {pdf_path}")
    else:
        print("\nFehler beim Erstellen des Vergleichs-PDFs.")

if __name__ == "__main__":
    main()
