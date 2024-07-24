'''
*
* first_setup.py: DCS Waypoint Editor - Program Settings Module             *
*                                                                           *
* Copyright (C) 2024 Atcz                                                   *
*                                                                           *
* This program is free software: you can redistribute it and/or modify it   *
* under the terms of the GNU General Public License as published by the     *
* Free Software Foundation, either version 3 of the License, or (at your    *
* option) any later version.                                                *
*                                                                           *
* This program is distributed in the hope that it will be useful, but       *
* WITHOUT ANY WARRANTY; without even the implied warranty of                *
* MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General  *
* Public License for more details.                                          *
*                                                                           *
* You should have received a copy of the GNU General Public License along   *
* with this program. If not, see <https://www.gnu.org/licenses/>.           *
'''

from configparser import ConfigParser
from shutil import copytree, rmtree
from src.logger import get_logger
from pathlib import Path
import PySimpleGUI as PyGUI
import os
import glob
import tempfile
import requests
import zipfile

DCS_BIOS_VERSION = '0.8.0'
DCS_BIOS_URL = "https://github.com/DCS-Skunkworks/dcs-bios/releases/download/v{}/DCS-BIOS_{}.zip"
aircraft = ["warthog", "apacheg", "apachep", "harrier", "hornet", "tomcat", "strikeeagle", "viper", "blackshark", "mirage"]
aircraft_name = ["A-10C", "AH-64D CPG", "AH-64D Pilot", "AV-8B", "F/A-18C", "F-14A/B", "F-15E", "F-16C", "Ka-50", "M-2000C"]

logger = get_logger(__name__)


def install_dcs_bios(dcs_path):
    try:
        with open(dcs_path + "Scripts\\Export.lua", "r") as f:
            filestr = f.read()
    except FileNotFoundError:
        filestr = str()

    with open(dcs_path + "Scripts\\Export.lua", "a") as f:
        if "dofile(lfs.writedir()..[[Scripts\\DCS-BIOS\\BIOS.lua]])" not in filestr:
            f.write(
                "\ndofile(lfs.writedir()..[[Scripts\\DCS-BIOS\\BIOS.lua]])\n")

    with tempfile.TemporaryDirectory() as tmp_dir:
        url = DCS_BIOS_URL.format(DCS_BIOS_VERSION, DCS_BIOS_VERSION)
        response = requests.get(url, stream=True)
        response.raise_for_status()

        with tempfile.TemporaryFile() as tmp_file:
            for block in response.iter_content(1024):
                tmp_file.write(block)

            with zipfile.ZipFile(tmp_file) as zip_ref:
                zip_ref.extractall(tmp_dir)

            try:
                rmtree(dcs_path + "Scripts\\DCS-BIOS", ignore_errors=True)
                copytree(tmp_dir + '\\DCS-BIOS', dcs_path + "Scripts\\DCS-BIOS")
                PyGUI.Popup(f'DCS-BIOS successfully downloaded and installed.')
            except:
                logger.debug(f"DCS Bios install failed.")


def detect_dcs_bios(dcs_path):
    dcs_bios_detected = False

    try:
        dcsbios_path = os.path.join(dcs_path, "Scripts", "DCS-BIOS")
        with open(dcs_path + "\\Scripts\\Export.lua", "r") as f:
            if r"dofile(lfs.writedir()..[[Scripts\DCS-BIOS\BIOS.lua]])" in f.read() and \
                    os.path.exists(dcsbios_path):
                dcs_bios_detected = True
    except FileNotFoundError:
        pass
    return dcs_bios_detected


def detect_the_way(dcs_path):
    the_way_detected = False

    try:
        theway_path = os.path.join(dcs_path, "Scripts", "**", "TheWay.lua")
        with open(dcs_path + "\\Scripts\\Export.lua", "r") as f:
            if r"dofile(TheWayLfs.writedir()..'Scripts/TheWay" in f.read() and \
                    any(glob.glob(theway_path, recursive=True)):
                the_way_detected = True
    except FileNotFoundError:
        pass
    return the_way_detected


def first_time_setup_gui(settings):
    section = "PREFERENCES"
    dcs_bios_detected = "Detected" if detect_dcs_bios(settings.get(section, 'dcs_path')) else "Not Detected"
    the_way_detected = "Detected" if detect_the_way(settings.get(section, 'dcs_path')) else "Not Detected"

    layout = [
        [PyGUI.Text("DCS User Folder Path:", (20,1), justification="right"),
         PyGUI.Input(settings.get(section, 'dcs_path'), key="dcs_path", enable_events=True),
         PyGUI.Button("Browse...", button_type=PyGUI.BUTTON_TYPE_BROWSE_FOLDER, target="dcs_path")],

        [PyGUI.Text("Tesseract.exe Path:", (20,1), justification="right"),
         PyGUI.Input(settings.get(section, 'tesseract_path'), key="tesseract_path"),
         PyGUI.Button("Browse...", button_type=PyGUI.BUTTON_TYPE_BROWSE_FILE, target="tesseract_path")],

        [PyGUI.Text("Capture Hotkey:", (20,1), justification="right"),
         PyGUI.Input(settings.get(section, 'capture_key'), key="capture_key")],

        [PyGUI.Text("Capture To Profile Hotkey:", (20,1), justification="right"),
         PyGUI.Input(settings.get(section, "quick_capture_hotkey"), key="quick_capture_hotkey")],

        [PyGUI.Text("Capture F10/F11 Hotkey:", (20,1), justification="right"),
         PyGUI.Input(settings.get(section, "camera_capture_hotkey"), key="camera_capture_hotkey")],

        [PyGUI.Text("Send To Aircraft Hotkey:", (20,1), justification="right"),
         PyGUI.Input(settings.get(section, 'enter_aircraft_hotkey'), key="enter_aircraft_hotkey")],

        [PyGUI.Text("Default Aircraft:", (20,1), justification="right"),
         PyGUI.Combo(values=aircraft_name, readonly=True,
            default_value=aircraft_name[aircraft.index(settings.get(section, 'default_aircraft'))],
            enable_events=True, key='default_aircraft', size=(30, 1))],

        [PyGUI.Text("PySimpleGUI Theme:", (20,1), justification="right"),
         PyGUI.Combo(values=PyGUI.theme_list(), readonly=True, default_value=settings.get(section, 'pysimplegui_theme'),
            enable_events=True, key='pysimplegui_theme', size=(30, 1))],

        [PyGUI.Text("Send To Aircraft Via:", (20,1), justification="right"),
         PyGUI.Combo(values=["DCS-BIOS", "TheWay.lua"], readonly=True, default_value=settings.get(section, 'enter_method'),
            enable_events=True, key='enter_method', size=(30, 1))],

        [PyGUI.Text("DCS-BIOS:", (20,1), justification="right"), PyGUI.Text(dcs_bios_detected, key="dcs_bios"),
         PyGUI.Button("Install", key="install_button", disabled=dcs_bios_detected == "Detected"),
         PyGUI.Button("Update to v" + DCS_BIOS_VERSION, key="update_button", disabled=dcs_bios_detected == "Not Detected")],

        [PyGUI.Text("The Way:", (20,1), justification="right"), PyGUI.Text(the_way_detected, key="the_way")],
    ]

    return PyGUI.Window("DCS Waypoint Editor Settings", [[PyGUI.Frame("Settings", layout)],
                                             [PyGUI.Button("Accept", key="accept_button", pad=((270, 1), 1),
                                                           disabled=dcs_bios_detected != "Detected")]], modal=True)


def first_time_setup(settings):
    section = "PREFERENCES"
    default_dcs_path = f"{str(Path.home())}\\Saved Games\\DCS\\"
    default_tesseract_path = f"{os.environ['PROGRAMW6432']}\\Tesseract-OCR\\tesseract.exe"
    default_aircraft = 'hornet'
    if settings is None:
        settings = ConfigParser()
        settings.add_section(section)
        settings.set(section, "grace_period", "5")
        settings.set(section, "button_release_short_delay", "0.2")
        settings.set(section, "button_release_medium_delay", "0.5")
        settings.set(section, "tesseract_path", default_tesseract_path)
        settings.set(section, "dcs_path", default_dcs_path)
        settings.set(section, "db_name", "profiles_new.db")
        settings.set(section, "capture_key", "ctrl+t")
        settings.set(section, "quick_capture_hotkey", "ctrl+shift+t")
        settings.set(section, "camera_capture_hotkey", "ctrl+shift+u")
        settings.set(section, "enter_aircraft_hotkey", '')
        settings.set(section, "log_raw_tesseract_output", "false")
        settings.set(section, "pysimplegui_theme", PyGUI.theme())
        settings.set(section, "default_aircraft", "hornet")
        settings.set(section, "enter_method", "DCS-BIOS")

    setup_logger = get_logger("setup")
    setup_logger.info("Running first time setup...")

    gui = first_time_setup_gui(settings)

    while True:
        event, values = gui.Read()
        if event is None:
            return False

        dcs_path = values.get("dcs_path").replace('/','\\')
        if dcs_path is not None and not dcs_path.endswith("\\"):
            dcs_path = dcs_path + "\\"

        if event == "accept_button":
            break
        elif event == "install_button":
            try:
                setup_logger.info("Installing DCS BIOS...")
                install_dcs_bios(dcs_path)
                gui.Element("install_button").Update(disabled=True)
                gui.Element("accept_button").Update(disabled=False)
                gui.Element("dcs_bios").Update(value="Installed")
            except (FileExistsError, FileNotFoundError, requests.HTTPError) as e:
                gui.Element("dcs_bios").Update(value="Install failed")
                setup_logger.error("DCS-BIOS failed to install", exc_info=True)
                PyGUI.Popup(f"DCS-BIOS failed to install:\n{e}")
        elif event == "update_button":
            try:
                setup_logger.info("Updating DCS BIOS...")
                install_dcs_bios(dcs_path)
                gui.Element("update_button").Update(disabled=True)
                gui.Element("dcs_bios").Update(value="Installed")
            except (FileExistsError, FileNotFoundError, requests.HTTPError) as e:
                gui.Element("dcs_bios").Update(value="Update failed")
                setup_logger.error("DCS-BIOS failed to update", exc_info=True)
                PyGUI.Popup(f"DCS-BIOS failed to update:\n{e}")
        elif event == "dcs_path":
            dcs_path.replace('/','\\')
            dcs_bios_detected = detect_dcs_bios(values["dcs_path"])
            the_way_detected = detect_the_way(values["dcs_path"])
            if dcs_bios_detected:
                gui.Element("install_button").Update(disabled=True)
                gui.Element("accept_button").Update(disabled=False)
                gui.Element("dcs_bios").Update(value="Detected")
            else:
                gui.Element("install_button").Update(disabled=False)
                gui.Element("accept_button").Update(disabled=True)
                gui.Element("dcs_bios").Update(value="Not detected")
            if the_way_detected:
                gui.Element("the_way").Update(value="Detected")
            else:
                gui.Element("the_way").Update(value="Not detected")
        elif event == "pysimplegui_theme":
            PyGUI.theme(values['pysimplegui_theme'])
            keep_new_theme = PyGUI.popup_get_text(
                                'This is {}\nChanges are applied after restart.'.format(values['pysimplegui_theme']),
                                title = 'Theme Sample', default_text = values['pysimplegui_theme'])
            if keep_new_theme is None:
                gui.Element("pysimplegui_theme").Update(settings.get(section, "pysimplegui_theme"))
                PyGUI.theme(settings.get(section, "pysimplegui_theme"))

    settings.set(section, "dcs_path", dcs_path or default_dcs_path)
    settings.set(section, "tesseract_path", values.get("tesseract_path") or default_tesseract_path)
    settings.set(section, "capture_key", values.get("capture_key") or "ctrl+t")
    settings.set(section, "quick_capture_hotkey", values.get("quick_capture_hotkey") or "ctrl+shift+t")
    settings.set(section, "camera_capture_hotkey", values.get("camera_capture_hotkey") or "ctrl+shift+u")
    settings.set(section, "enter_aircraft_hotkey", values.get("enter_aircraft_hotkey") or '')
    settings.set(section, "pysimplegui_theme", values.get("pysimplegui_theme") or PyGUI.theme())
    settings.set(section, "default_aircraft", aircraft[aircraft_name.index(values.get("default_aircraft"))] or "hornet")
    settings.set(section, "enter_method", values.get("enter_method") or "DCS-BIOS")

    with open("settings.ini", "w+") as f:
        settings.write(f)

    setup_logger.info("First time setup completed succesfully")
    gui.Close()
    return True
