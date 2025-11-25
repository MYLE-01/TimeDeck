# utils/paths.py
import os
import sys
import zipfile
#========================================================
UNC_PATH = r"\\zeus\data\HWR2-Whareroa\Powders\PMP\Data"
#========================================================
def resolve_base_dir():
    if os.path.exists(UNC_PATH):
        return UNC_PATH
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    # Anchor from project root, not utils/
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

BASE_DIR = resolve_base_dir()

CONFIGS_DIR = os.path.join(BASE_DIR, "configs")
CONFIG_DIR = CONFIGS_DIR  # Alias for backward compatibility
CONFIG_DIRS = CONFIGS_DIR  # Alias for backward compatibility   

JOB_TITLES_FILE = os.path.join(CONFIGS_DIR, "jobtitle.json")

if getattr(sys, "frozen", False):
    TEMPLATES_DIR = os.path.join(sys._MEIPASS, "templates")
    STATIC_DIR = os.path.join(sys._MEIPASS, "static")
    IMAGES_DIR = os.path.join(sys._MEIPASS, "images")
    QR_DIR = os.path.join(os.path.dirname(sys.executable),"configs", "images", "qrcodes")
    LOGO_DIR = os.path.join(os.path.dirname(sys.executable),"configs", "images")

else:
    TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
    STATIC_DIR = os.path.join(BASE_DIR, "static")
    IMAGES_DIR = os.path.join(BASE_DIR, "images")
    QR_DIR = os.path.join(BASE_DIR, "images", "qrcodes")
    LOGO_DIR = os.path.join(BASE_DIR, "images")

def zip_my_files(file_list, output_zip):

    with zipfile.ZipFile(output_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for filepath in file_list:
            if os.path.isfile(filepath):
                arcname = os.path.basename(filepath)  # just the filename inside the zip
                zipf.write(filepath, arcname)
                print(f"✅ Added: {arcname}")
            else:
                print(f"⚠️ Skipped (not found): {filepath}")

def do_the_zip(me):

    files_to_zip = [
        os.path.join(CONFIGS_DIR, "config.json"),
        os.path.join(CONFIGS_DIR, "shifts.json"),
        os.path.join(CONFIGS_DIR, "jobtitle.json"),
        os.path.join(CONFIGS_DIR, "leave.json"),
        os.path.join(CONFIGS_DIR, "sick.json"),
        os.path.join(CONFIGS_DIR, f"EMP_{me.emp_id}.json"),
        os.path.join(CONFIGS_DIR, f"roster_{me.emp_id}.json"),
    ]

    # Add all files from a folder (e.g., ASSETS_DIR)
    folder_to_include = os.path.join(BASE_DIR, "images")
    for root, _, files in os.walk(folder_to_include):
        for file in files:
            full_path = os.path.join(root, file)
            files_to_zip.append(full_path)

    output_zip_path = os.path.join(BASE_DIR, "time_deck_for_home.zip")
    zip_my_files(files_to_zip, output_zip_path)
    print(f"📦 Backup created at: {output_zip_path}")