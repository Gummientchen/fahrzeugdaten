# export.py
import sys
import os
from datetime import datetime
from fpdf import FPDF
from fpdf.enums import XPos, YPos

# Import refactored components
import config
import database
import formatting
import translation # Import the new translation module
from utils import clean_sql_identifier, get_resource_path

# --- PDF Generation Class (Specific to Single Export) ---
class PDFSingle(FPDF):
    def header(self):
        # Set font (use the default family set during PDF creation)
        self.set_font(style='I', size=8)
        page_w = self.w - self.l_margin - self.r_margin
        # Header Text (Left Aligned) - Use translated title
        self.cell(page_w / 2, 10, translation._("pdf_title_single"), border=0, align='L')
        # Date (Right Aligned) - Use translated "Generated:"
        generation_date = datetime.now().strftime("%d.%m.%Y")
        generated_text = translation._("pdf_generated_on")
        self.cell(page_w / 2, 10, f"{generated_text} {generation_date}", border=0, align='R', new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        # Line break and separator line
        self.ln(2)
        self.set_draw_color(180, 180, 180)
        self.set_line_width(config.PDF_DIVIDER_THICKNESS)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(5) # Space after header line

    def add_vehicle_details(self, formatted_data):
        """Adds the main vehicle details to the PDF."""
        if not formatted_data:
            self.set_font_size(10)
            # Use translated message
            self.cell(0, 10, translation._("pdf_no_data"), border=0, align='C', new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            return

        # --- Main Header (TG_Code, Marke, Typ) ---
        self.set_font(self.font_family, 'B', config.PDF_FONT_SIZE_HEADER) # Use self.font_family
        # Safely get header values using original names
        tg_code_val = formatted_data.get('TG_Code', 'N/A')
        marke_val = formatted_data.get('Marke', 'N/A')
        typ_val = formatted_data.get('Typ', 'N/A')
        header_text = f"{tg_code_val} - {marke_val} - {typ_val}"
        self.cell(0, 8, header_text, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L')
        self.ln(8) # Space after header

        # --- Body Content ---
        page_width = self.w - self.l_margin - self.r_margin
        value_width = page_width - config.PDF_LABEL_WIDTH

        if value_width <= 0:
             print("Error: Calculated width for value column is zero or negative.")
             return # Cannot proceed

        for item_name in config.DISPLAY_ORDER_WITH_DIVIDERS:
            if item_name == config.DIVIDER_MARKER:
                self.ln(config.PDF_DIVIDER_MARGIN)
                self.set_draw_color(180, 180, 180)
                self.set_line_width(config.PDF_DIVIDER_THICKNESS)
                self.line(self.l_margin, self.get_y(), self.l_margin + page_width, self.get_y())
                self.ln(config.PDF_DIVIDER_MARGIN)
                continue

            # Skip header items already printed
            if item_name in ['TG_Code', 'Marke', 'Typ']:
                continue

            # Get the pre-formatted value
            display_value = formatted_data.get(item_name, "") # Default to empty string

            # --- Add Label and Value to PDF ---
            self.set_x(self.l_margin)
            start_y = self.get_y()

            # Label (Bold) - Translate the item_name
            self.set_font(self.font_family, 'B', config.PDF_FONT_SIZE_BODY) # Use self.font_family
            translated_label = translation._(item_name) # Translate the label
            self.multi_cell(config.PDF_LABEL_WIDTH, config.PDF_LINE_HEIGHT, f"{translated_label}:",
                            border=0, align='L', new_x=XPos.RIGHT, new_y=YPos.TOP)
            label_end_y = self.get_y() # Y position after label cell

            # Value (Regular) - Position next to label
            self.set_xy(self.l_margin + config.PDF_LABEL_WIDTH, start_y) # Set position explicitly
            self.set_font(self.font_family, '', config.PDF_FONT_SIZE_BODY) # Use self.font_family
            self.multi_cell(value_width, config.PDF_LINE_HEIGHT, display_value,
                            border=0, align='L', new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            value_end_y = self.get_y() # Y position after value cell

            # Ensure the next line starts below the taller of the two cells
            new_y = max(label_end_y, value_end_y, start_y + config.PDF_LINE_HEIGHT)
            self.set_y(new_y)


# --- Main PDF Creation Function ---
def create_single_pdf(raw_data_row, output_filename):
    """Creates a formatted PDF for a single vehicle."""
    if not raw_data_row:
        print("Error: No data provided to create PDF.")
        return False

    try:
        # 1. Format the raw data (formatting.py now handles value translations)
        formatted_data = formatting.format_vehicle_data(raw_data_row)
        if not formatted_data:
             print("Error: Formatting failed, cannot create PDF.")
             return False

        # 2. Initialize PDF
        pdf = PDFSingle()
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
        except Exception as font_err: # Catch FPDF font errors or other issues
            print(f"Warning: Failed to load DejaVu font ({font_err}). Using fallback {font_family_to_use}.")

        # Set the chosen font family (either DejaVu or Fallback)
        pdf.set_font(font_family_to_use, '', config.PDF_FONT_SIZE_BODY)


        pdf.add_page()
        pdf.set_margins(left=15, top=15, right=15)
        pdf.set_auto_page_break(auto=True, margin=15)

        # 3. Add content using the formatted data
        pdf.add_vehicle_details(formatted_data)

        # 4. Save the PDF
        pdf.output(output_filename)
        print(f"PDF exported successfully to '{output_filename}'")
        return True

    except ImportError:
         print("Error: FPDF library not found. Please install it using: pip install fpdf2")
         return False
    except Exception as e:
        print(f"An error occurred during PDF generation: {e}")
        import traceback
        traceback.print_exc() # Print detailed traceback for debugging
        return False


# --- Main Execution (CLI) ---
# (CLI part remains unchanged, uses the updated create_single_pdf)
if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: python {os.path.basename(__file__)} <TG-Code>")
        sys.exit(1)

    tg_code_input = sys.argv[1]

    print(f"Searching for TG-Code: {tg_code_input}...")
    raw_data_row = database.search_by_tg_code(tg_code_input)

    if raw_data_row:
        try:
            # Ensure export directory exists
            os.makedirs(config.EXPORT_DIR_SINGLE, exist_ok=True)

            # Create filename
            cleaned_name_part = clean_sql_identifier(tg_code_input)
            safe_filename_part = cleaned_name_part.lstrip('_') # Avoid leading underscore
            base_filename = f"{safe_filename_part}.pdf"
            full_pdf_path = os.path.join(config.EXPORT_DIR_SINGLE, base_filename)

            print(f"Data found. Generating PDF: '{full_pdf_path}'...")
            # Initialize translations for CLI run (using default language)
            translation.initialize_translations()
            success = create_single_pdf(raw_data_row, full_pdf_path)
            if not success:
                 sys.exit(1) # Exit with error code if PDF generation failed

        except OSError as e:
            print(f"Error creating directory '{config.EXPORT_DIR_SINGLE}': {e}")
            sys.exit(1)
        except Exception as e:
             print(f"An error occurred: {e}")
             sys.exit(1)
    else:
        print(f"No data found for TG-Code '{tg_code_input}'.")
        sys.exit(1)
