# config.py
import os
import re
import sys # <--- Import sys

# --- Determine Base Directory ---
# If running as a bundled executable (frozen), use the directory of the executable.
# Otherwise (running as script), use the directory of this config file.
if getattr(sys, 'frozen', False):
    # Running as bundled executable (e.g., via PyInstaller)
    # sys.executable points to the executable itself
    BASE_DIR = os.path.dirname(sys.executable)
    print(f"INFO: Running bundled. Persistent BASE_DIR set to: {BASE_DIR}")
else:
    # Running as a script
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    print(f"INFO: Running as script. Persistent BASE_DIR set to: {BASE_DIR}")

# --- Persistent File/Directory Paths (Relative to BASE_DIR) ---
# These paths will now be relative to the executable's location when bundled.
DATA_DIR = BASE_DIR
EXPORT_DIR = os.path.join(BASE_DIR, "export")
EXPORT_DIR_SINGLE = EXPORT_DIR
EXPORT_DIR_COMPARE = EXPORT_DIR
DATABASE_NAME = 'emissionen.db'
DATABASE_PATH = os.path.join(BASE_DIR, DATABASE_NAME) # DB in BASE_DIR
INPUT_FILENAME = "emissionen.txt"
INPUT_FILE_PATH = os.path.join(DATA_DIR, INPUT_FILENAME) # Downloaded file in DATA_DIR

# --- Bundled Resource Paths (Relative to where the script *was*) ---
# These paths are used by get_resource_path, which handles _MEIPASS correctly.
# Define them relative to the original script structure.
_SCRIPT_DIR = os.path.abspath(os.path.dirname(__file__)) # Original script dir
LANG_DIR = os.path.join(_SCRIPT_DIR, "lang")
FONT_DIR = os.path.join(_SCRIPT_DIR, "fonts")
FONT_REGULAR_PATH = os.path.join(FONT_DIR, "DejaVuSans.ttf")
FONT_BOLD_PATH = os.path.join(FONT_DIR, "DejaVuSans-Bold.ttf")
FONT_ITALIC_PATH = os.path.join(FONT_DIR, "DejaVuSans-Oblique.ttf")
FONT_BOLD_ITALIC_PATH = os.path.join(FONT_DIR, "DejaVuSans-BoldOblique.ttf")


# --- Download ---
DOWNLOAD_URL = "https://opendata.astra.admin.ch/ivzod/2000-Typengenehmigungen_TG_TARGA/2200-Basisdaten_TG_ab_1995/emissionen.txt"

# --- Network Timeouts ---
STARTUP_CHECK_TIMEOUT = 10 # Seconds for the initial HEAD request check
DOWNLOAD_TIMEOUT = 3600     # Seconds for the full file download

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

# Desired Display Order with Dividers (Original names)
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
PDF_FONT_FALLBACK = "Helvetica"
PDF_FONT_NAME_DEJAVU = "DejaVu"
PDF_FONT_SIZE_TITLE = 16
PDF_FONT_SIZE_HEADER = 12
PDF_FONT_SIZE_BODY = 10
PDF_LABEL_WIDTH = 60
PDF_LINE_HEIGHT = 6
PDF_DIVIDER_THICKNESS = 0.2
PDF_DIVIDER_MARGIN = 3

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
    "1337": "1337 (Leetspeak)",
    "x-piglatin": "Igpay Atinlay (Pig Latin)"
}

# --- Derived Constants ---
def _clean_sql_identifier_local(name):
    """Cleans a string to be a valid SQL identifier (table/column name)."""
    if not isinstance(name, str): return ""
    name = re.sub(r'[ /.\-+()]+', '_', name)
    name = name.replace('ET_THC_NOx', 'ET_THC_NOx')
    name = name.replace('ZT_THC_NOx', 'ZT_THC_NOx')
    name = name.strip('_')
    if name and name[0].isdigit(): name = '_' + name
    return name

OMIT_COLUMNS_CLEANED = set(_clean_sql_identifier_local(col) for col in OMIT_COLUMNS_ORIGINAL)

# --- Final Check and Print ---
print(f"INFO: Database path set to: {DATABASE_PATH}")
print(f"INFO: Data directory set to: {DATA_DIR}")
print(f"INFO: Export directory set to: {EXPORT_DIR}")
print(f"INFO: Language directory (relative for resources) set to: {LANG_DIR}")
print(f"INFO: Font directory (relative for resources) set to: {FONT_DIR}")
