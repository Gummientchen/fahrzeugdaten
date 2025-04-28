# config.py
import os
import re

# --- File/Directory Paths ---
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
EXPORT_DIR = os.path.join(BASE_DIR, "export") # General export dir
EXPORT_DIR_SINGLE = EXPORT_DIR # Can be the same or different if needed
EXPORT_DIR_COMPARE = EXPORT_DIR
LANG_DIR = os.path.join(BASE_DIR, "lang")
DATABASE_NAME = 'emissionen.db'
DATABASE_PATH = os.path.join(BASE_DIR, DATABASE_NAME) # DB in root project dir
INPUT_FILENAME = "emissionen.txt"
INPUT_FILE_PATH = os.path.join(DATA_DIR, INPUT_FILENAME)
# Path for DejaVu fonts (assuming they are in a 'fonts' subdirectory)
# Adjust this path if your fonts are located elsewhere
FONT_DIR = os.path.join(BASE_DIR, "fonts")
FONT_REGULAR_PATH = os.path.join(FONT_DIR, "DejaVuSans.ttf")
FONT_BOLD_PATH = os.path.join(FONT_DIR, "DejaVuSans-Bold.ttf")
FONT_ITALIC_PATH = os.path.join(FONT_DIR, "DejaVuSans-Oblique.ttf")
FONT_BOLD_ITALIC_PATH = os.path.join(FONT_DIR, "DejaVuSans-BoldOblique.ttf")


# --- Download ---
DOWNLOAD_URL = "https://opendata.astra.admin.ch/ivzod/2000-Typengenehmigungen_TG_TARGA/2200-Basisdaten_TG_ab_1995/emissionen.txt"

# --- Importer Settings ---
FILE_ENCODING = 'windows-1252'
DB_ENCODING = 'utf-8'
DELIMITER = '\t'
NORMALIZE_COLUMNS = [
    "Marke", "Getriebe", "Motormarke", "Motortyp", "Treibstoff",
    "Abgasreinigung", "Antrieb", "Anzahl_Achsen_Räder", "AbgasCode",
    "Emissionscode", "GeräuschCode"
]

# --- Formatting & Display ---
# Dictionary mapping column names (as stored in DB, cleaned) to units
UNITS_MAP = {
    "Leergewicht_von": "kg", "Leergewicht_bis": "kg", "Garantiegewicht_von": "kg",
    "Garantiegewicht_bis": "kg", "Gesamtzuggewicht_bis": "kg", "Gesamtzuggewicht_von": "kg",
    "Vmax_von": "km/h", "Vmax_bis": "km/h", "Hubraum": "ccm", "Leistung": "kW",
    "Leistung_bei_n_min": "rpm", "Drehmoment": "Nm", "Drehmoment_bei_n_min": "rpm",
    "Fahrgeräusch": "dbA", "Standgeräusch": "dbA", "Standgeräusch_bei_n_min": "rpm"
}

# Conversion factor
KW_TO_PS = 1.35962

# Date Formats
HOMOLOGATIONSDATUM_INPUT_FORMAT = '%Y%m%d'
HOMOLOGATIONSDATUM_OUTPUT_FORMAT = '%d.%m.%Y'

# Columns to Omit from general display/export (Original names)
OMIT_COLUMNS_ORIGINAL = [
    "ET_CO", "ET_NMHC", "ET_NOx", "ET_PA", "ET_PA_Exp", "ET_PM",
    "ET_THC", "ET_THC_NOx", "ET_T_IV_THC", "ET_T_VI_CO", "ET_T_VI_THC",
    "ScCo2", "ScConsumption", "ScNh3", "ScNo2", "TC_CO2", "TC_Consumption",
    "TC_NH3", "TC_NO2", "ZT_CO", "ZT_NMHC", "ZT_NOx", "ZT_PA", "ZT_PA_Exp",
    "ZT_PM", "ZT_THC", "ZT_THC_NOx", "ZT_T_IV_THC", "ZT_T_VI_CO", "ZT_T_VI_THC",
    "ZT_NMHC", "ZT_NOx", "ZT_AbgasCode"
]

# --- REMOVED Translation Maps ---
# ANTRIEB_MAP = { ... } # Now handled by translation files
# TREIBSTOFF_MAP = { ... } # Now handled by translation files

# Desired Display Order with Dividers (Original names)
# These names will be used as KEYS for translation lookups
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

# --- PDF Settings ---
# PDF_TITLE_SINGLE = "Fahrzeugdatenblatt" # Now handled by translation key "pdf_title_single"
# PDF_TITLE_COMPARE = "Fahrzeugvergleich" # Now handled by translation key "pdf_title_compare"
PDF_FONT_FALLBACK = "Helvetica" # Fallback if DejaVu fails
PDF_FONT_NAME_DEJAVU = "DejaVu" # Name to use for DejaVu in FPDF
PDF_FONT_SIZE_TITLE = 16
PDF_FONT_SIZE_HEADER = 12
PDF_FONT_SIZE_BODY = 10
PDF_LABEL_WIDTH = 60 # Width for the label column in mm (Single Export)
PDF_LINE_HEIGHT = 6 # Line height in mm (Single Export)
PDF_DIVIDER_THICKNESS = 0.2 # Thickness of divider lines in mm
PDF_DIVIDER_MARGIN = 3 # Space above/below divider line in mm

# --- GUI Settings ---
DEFAULT_LANG = "en"
SUPPORTED_LANGS = {
    "en": "English",
    "de": "Deutsch",
    "fr": "Français",
    "it": "Italiano",
    "es": "Español",
    "pt": "Português",
    "nl": "Nederlands",
    "pl": "Polski",
    "no": "Norsk",
    "sv": "Svenska",
    "fi": "Suomi",
    "tlh": "tlhIngan Hol (Klingon)",
    "na": "Na'vi",
    "sjn": "Sindarin (Elvish)",
    "1337": "1337 (Leetspeak)"
}

# --- Derived Constants ---
# Helper function needed here to calculate OMIT_COLUMNS_CLEANED
def _clean_sql_identifier_local(name):
    """Cleans a string to be a valid SQL identifier (table/column name)."""
    if not isinstance(name, str): return ""
    name = re.sub(r'[ /.\-+()]+', '_', name)
    # Specific replacements needed *before* stripping underscore if they create leading/trailing ones
    name = name.replace('ET_THC_NOx', 'ET_THC_NOx') # Keep as is
    name = name.replace('ZT_THC_NOx', 'ZT_THC_NOx') # Keep as is
    name = name.strip('_')
    if name and name[0].isdigit(): name = '_' + name
    return name

OMIT_COLUMNS_CLEANED = set(_clean_sql_identifier_local(col) for col in OMIT_COLUMNS_ORIGINAL)
