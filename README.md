# Fahrzeugdaten Search

## General usage

Install requirements.txt

```powershell
pip install -r requirements.txt
```

Run gui.py

```powershell
python gui.py
```

## Use in terminal

Execute the import.py script. It automatically downloads the newest "emissionen.txt" file from OpenData ([emissionen.txt]("https://opendata.astra.admin.ch/ivzod/2000-Typengenehmigungen_TG_TARGA/2200-Basisdaten_TG_ab_1995/emissionen.txt"))

```python
python import.py
```

Run the search script:

```python
python search.py TYPENGENEHMIGUNG
```

## Build executable with pyinstaller

Install pyinstaller

```powershell
pyinstaller --clean --onefile --windowed --name Fahrzeugdaten gui.py --add-data "lang;lang"
```

The executable "Fahrzeutdaten.exe" will be created in the dist folder.
