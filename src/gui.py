from src.objects import Profile, Waypoint, MSN, load_base_file, generate_default_bases
from src.first_setup import first_time_setup, detect_the_way
from src.capture import capture_map_coords, parse_map_coords_string
from src.logger import get_logger
from peewee import DoesNotExist
from LatLon23 import LatLon, Longitude, Latitude
import src.pymgrs as mgrs
import pytesseract
import keyboard
import os
import subprocess
import json
import socket
import urllib.request
import urllib.error
import webbrowser
import base64
import pyperclip
from slpp import slpp as lua
import PySimpleGUI as PyGUI
import winsound
import zlib

UX_SND_ERROR = "data/ux_error.wav"
UX_SND_SUCCESS = "data/ux_success.wav"

def json_zip(j):
    j = base64.encodebytes(
        zlib.compress(
            j.encode('utf-8')
        )
    ).decode('ascii')
    return j


def json_unzip(j):
    return zlib.decompress(base64.b64decode(j)).decode('utf-8')


def strike(text):
    result = '\u0336'
    for i, c in enumerate(text):
        result = result + c
        if i != len(text)-1:
            result = result + '\u0336'
    return result


def unstrike(text):
    return text.replace('\u0336', '')


def exception_gui(exc_info):
    return PyGUI.PopupOK("An exception occured and the program terminated execution:\n\n" + exc_info)


def check_version(current_version):
    version_url = "https://raw.githubusercontent.com/atcz/DCSWaypointEditor/master/release_version.txt"
    releases_url = "https://github.com/atcz/DCSWaypointEditor/releases"

    try:
        with urllib.request.urlopen(version_url) as response:
            if response.code == 200:
                html = response.read()
            else:
                return False
    except (urllib.error.HTTPError, urllib.error.URLError):
        return False

    new_version = html.decode("utf-8")
    if new_version[1:6] > current_version[1:6]:
        popup_answer = PyGUI.PopupYesNo(
            f"New version available: {new_version}\nDo you wish to update?")

        if popup_answer == "Yes":
            webbrowser.open(releases_url)
            return True
        else:
            return False


def try_get_setting(settings, setting_name, setting_fallback, section="PREFERENCES"):
    if settings.has_option(section, setting_name):
        return settings.get(section, setting_name)
    else:
        settings[section][setting_name] = setting_fallback
        with open("settings.ini", "w") as configfile:
            settings.write(configfile)
        return setting_fallback


class GUI:
    def __init__(self, editor, software_version):
        self.logger = get_logger("gui")
        self.editor = editor
        self.captured_map_coords = None
        self.profile = Profile('')
        self.aircraft = ["warthog", "apacheg", "apachep", "harrier", "hornet", "tomcat", "viper", "blackshark", "mirage"]
        self.aircraft_name = ["A-10C", "AH-64D CPG", "AH-64D Pilot", "AV-8B", "F/A-18C", "F-14A/B", "F-16C", "Ka-50", "M-2000C"]
        self.wp_types = ["WP", "MSN", "FP", "ST", "IP", "DP", "HA", "HB", "HZ", "CM", "TG"]
        self.quick_capture = False
        self.values = None
        self.capturing = False
        self.enable_the_way = detect_the_way(self.editor.settings.get('PREFERENCES', 'dcs_path'))
        self.capture_key = try_get_setting(self.editor.settings, "capture_key", "ctrl+t")
        self.quick_capture_hotkey = try_get_setting(self.editor.settings, "quick_capture_hotkey", "ctrl+shift+t")
        self.camera_capture_hotkey = try_get_setting(self.editor.settings, "camera_capture_hotkey", "ctrl+shift+u")
        self.enter_aircraft_hotkey = try_get_setting(self.editor.settings, "enter_aircraft_hotkey", "")
        self.save_debug_images = try_get_setting(self.editor.settings, "save_debug_images", "false")
        self.pysimplegui_theme = try_get_setting(self.editor.settings, "pysimplegui_theme", PyGUI.theme())
        self.default_aircraft = try_get_setting(self.editor.settings, "default_aircraft", "hornet")
        self.enter_method = try_get_setting(self.editor.settings, "enter_method", "DCS-BIOS")
        self.software_version = software_version
        self.is_focused = True
        self.scaled_dcs_gui = False
        self.selected_wp_type = "WP"
        self.profile.aircraft = self.default_aircraft
        self.editor.set_driver(self.default_aircraft)

        try:
            with open(f"{self.editor.settings.get('PREFERENCES', 'dcs_path')}\\Config\\options.lua", "r") as f:
                dcs_settings = lua.decode(f.read().replace("options = ", ""))
                self.scaled_dcs_gui = dcs_settings["graphics"]["scaleGui"]
        except (FileNotFoundError, ValueError, TypeError):
            self.logger.error("Failed to decode DCS settings", exc_info=True)

        tesseract_path = self.editor.settings['PREFERENCES'].get(
            'tesseract_path', "tesseract")
        self.logger.info(f"Tesseract path is: {tesseract_path}")
        pytesseract.pytesseract.tesseract_cmd = tesseract_path
        try:
            self.tesseract_version = pytesseract.get_tesseract_version()
            self.capture_status = "Status: Not capturing"
            self.capture_button_disabled = False
        except pytesseract.pytesseract.TesseractNotFoundError:
            self.tesseract_version = None
            self.capture_status = "Status: Tesseract not found"
            self.capture_button_disabled = True

        self.logger.info(f"Tesseract version is: {self.tesseract_version}")
        self.window = self.create_gui()
        keyboard.add_hotkey(self.quick_capture_hotkey, self.toggle_quick_capture)
        keyboard.add_hotkey(self.camera_capture_hotkey, self.toggle_camera_capture)
        if self.enter_aircraft_hotkey != '':
            keyboard.add_hotkey(self.enter_aircraft_hotkey, self.enter_coords_to_aircraft)

    @staticmethod
    def get_profile_names():
        return [profile.name for profile in Profile.list_all()]

    def create_gui(self):
        self.logger.debug("Creating GUI")
        
        PyGUI.theme(self.pysimplegui_theme)

        lattype_col = [
            [PyGUI.Radio("N", group_id="lat_type", default=True, enable_events=True, key="North")],
            [PyGUI.Radio("S", group_id="lat_type", enable_events=True, key="South")]
        ]

        latitude_col1 = [
            [PyGUI.Text("Deg", pad=((9,5),3))],
            [PyGUI.InputText(size=(5, 1), key="latDeg", 
                             pad=((9,5),3), enable_events=True)],
        ]

        latitude_col2 = [
            [PyGUI.Text("Min")],
            [PyGUI.InputText(size=(5, 1), key="latMin", enable_events=True)],
        ]

        latitude_col3 = [
            [PyGUI.Text("Sec")],
            [PyGUI.InputText(size=(5, 1), key="latSec",
                             pad=(5, 3), enable_events=True)],
        ]

        lontype_col = [
            [PyGUI.Radio("E", group_id="lon_type", default=True, enable_events=True, key="East")],
            [PyGUI.Radio("W", group_id="lon_type", enable_events=True, key="West")]
        ]

        longitude_col1 = [
            [PyGUI.Text("Deg")],
            [PyGUI.InputText(size=(5, 1), key="lonDeg", enable_events=True)],
        ]

        longitude_col2 = [
            [PyGUI.Text("Min")],
            [PyGUI.InputText(size=(5, 1), key="lonMin", enable_events=True)],
        ]

        longitude_col3 = [
            [PyGUI.Text("Sec")],
            [PyGUI.InputText(size=(5, 1), key="lonSec",
                             pad=(5, 3), enable_events=True)],
        ]

        elevation_col1 = [
            [PyGUI.Text("Feet")],
            [PyGUI.InputText(size=(6, 1), key="elevFeet", enable_events=True)]
        ]

        elevation_col2 = [
            [PyGUI.Text("Meters")],
            [PyGUI.InputText(size=(6, 1), key="elevMeters", enable_events=True)]
        ]

        frameelevationlayout = [
            [PyGUI.Column(elevation_col1, pad=(9, 7)),
             PyGUI.Column(elevation_col2)],
        ]

        framedatalayoutcol2 = [
            [PyGUI.Text("Aircraft Type")],
            [PyGUI.Combo(values=self.aircraft_name, readonly=True, enable_events=True,
                         key='aircraftSelector', size=(18,1))] ,
            [PyGUI.Text("Name")],
            [PyGUI.InputText(size=(20, 1), key="msnName", pad=(5, (2, 2)))],
            [PyGUI.Text("Grid Reference")],
            [PyGUI.InputText(size=(20, 1), key="mgrs", enable_events=True, pad=(5, (2, 6)))],
        ]

        framepresetlayout = [
            [PyGUI.Text("Select preset location:")],
            [PyGUI.Combo(values=[""] + sorted(self.editor.default_bases),
                         readonly=False, enable_events=True, key='baseSelector'),
             PyGUI.Button(button_text="F", key="presetFilter")]
        ]

        frameregionlayout = [
            [PyGUI.Text("Select region:")],
            [PyGUI.Combo(values=[""] + sorted(self.editor.base_files), readonly=True,
                         enable_events=True, key='regionSelector', size=(19,1), pad=(6, 6))],
        ]

        framewptypelayout = [
            [PyGUI.Combo(values=self.wp_types, default_value=self.wp_types[0], readonly=True, enable_events=True,
                         key='wpType', size=(7,len(self.wp_types))),
             PyGUI.Text("Sequence:", pad=((0, 1), 3),
                        key="sequence_text", auto_size_text=False, size=(8, 1)),
             PyGUI.Combo(values=("None", 1, 2, 3), default_value="None",
                         auto_size_text=False, size=(5, 1), readonly=True,
                         key="sequence", enable_events=True)],
            [PyGUI.Button("Capture Coordinates", disabled=self.capture_button_disabled, key="capture",
                size=(22, 1), pad=(10, (10, 3)))],
            [PyGUI.Button("Capture To Profile", disabled=self.capture_button_disabled, key="quick_capture",
                size=(22, 1), pad=(10, (3, 3)))],
            [PyGUI.Button("Capture F10/F11 View", disabled=(not self.enable_the_way), key="camera_capture",
                size=(22, 1), pad=(10, (3, 3)))],
            [PyGUI.Text(self.capture_status, key="capture_status", auto_size_text=False, 
                size=(20, 1), pad=(10, 3))],
        ]

        framelongitude = PyGUI.Frame("Longitude", [
            [PyGUI.Column(lontype_col), PyGUI.Column(longitude_col1),
             PyGUI.Column(longitude_col2), PyGUI.Column(longitude_col3)]
        ])

        framelatitude = PyGUI.Frame("Latitude", [
            [PyGUI.Column(lattype_col), PyGUI.Column(latitude_col1),
             PyGUI.Column(latitude_col2), PyGUI.Column(latitude_col3)]
        ])

        frameelevation = PyGUI.Frame(
            "Elevation", frameelevationlayout)

        framepositionlayout = [
            [framelatitude,
             framelongitude,
             frameelevation],
        ]

        frameposition = PyGUI.Frame("Position", framepositionlayout)
        framepreset = PyGUI.Frame("Preset", framepresetlayout)
        frameregion = PyGUI.Frame("Region", frameregionlayout)
        framedata = PyGUI.Frame("Data", framedatalayoutcol2)
        framewptype = PyGUI.Frame("Waypoint", framewptypelayout)

        col0 = [
            [PyGUI.Text("Select profile:")],
            [PyGUI.Combo(values=[""] + sorted(self.get_profile_names()), readonly=False,
                         enable_events=True, key='profileSelector', size=(29, 1)),
             PyGUI.Button(button_text="F", key="profileFilter")],
            [PyGUI.Listbox(values=list(), size=(33, 14),
                           enable_events=True, key='activesList')],
            # [PyGUI.Button("Move up", size=(12, 1)),
            # PyGUI.Button("Move down", size=(12, 1))],
        ]

        col1 = [
            [framepreset, frameregion],
            [framedata, framewptype],
            [PyGUI.Button("Add", size=(8, 1)),
             PyGUI.Button("Update", size=(8, 1)),
             PyGUI.Button("Remove", size=(8, 1)),
             PyGUI.Button("Send To Aircraft", size=(14, 1), key="Send")],
        ]

        menudef = [['&File',
                    ['&Settings', '---', '&Run Target Jar', '---', 'E&xit']],
                   ['&Profile',
                    ['&Save Profile', '&Delete Profile', 'Save Profile &As...', '---',
                        "&Import", ["Paste as &String from clipboard", "Load from &Encoded file", "---",
                                    "Import NS430 from clipboard", "Import NS430 from file"],
                        "&Export", ["Copy as &String to clipboard", "Copy plain &Text to clipboard",
                                    "Save as &Encoded file"]]],
                   ['&?',
                    ['&About']]
                  ]

        colmain1 = [
            [PyGUI.MenuBar(menudef)],
            [PyGUI.Column(col1)],
        ]

        layout = [
            [PyGUI.Column(col0), PyGUI.Column(colmain1)],
            [frameposition],
            [PyGUI.Text(f"Version: {self.software_version}")]
        ]

        return PyGUI.Window('DCS Waypoint Editor', layout, finalize=True)

    def set_sequence_station_selector(self, mode, station=None):
        if mode is None:
            self.window.Element("sequence_text").Update(value="Sequence:")
            self.window.Element("sequence").Update(
                values=("None", 1, 2, 3), value="None", disabled=True)
        if mode == "sequence":
            self.window.Element("sequence_text").Update(value="Sequence:")
            self.window.Element("sequence").Update(
                values=("None", 1, 2, 3), value="None", disabled=False)
            self.values["sequence"] = "None"
        elif mode == "station":
            if station is not None:
                select = station
            else:
                select = 8
            self.window.Element("sequence_text").Update(value="    Station:")
            self.window.Element("sequence").Update(
                values=(8, 2, 7, 3), value=select, disabled=False)
            self.values["sequence"] = select

    def update_position(self, position=None, elevation=None, name=None, update_mgrs=True, aircraft=None,
                        waypoint_type=None, station=None):

        if position is not None:
            latdeg = round(position.lat.degree)
            latmin = round(position.lat.minute)
            latsec = round(position.lat.second, 2)

            londeg = round(position.lon.degree)
            lonmin = round(position.lon.minute)
            lonsec = round(position.lon.second, 2)
            mgrs_str = mgrs.encode(mgrs.LLtoUTM(
                position.lat.decimal_degree, position.lon.decimal_degree), 5)
        else:
            latdeg = ""
            latmin = ""
            latsec = ""

            londeg = ""
            lonmin = ""
            lonsec = ""
            mgrs_str = ""

        # Set N/S/E/W flags and deg/min/sec to absolute value for display
        if latdeg == "" or latdeg >= 0:
            self.window.Element("North").Update(True)
        else:
            self.window.Element("South").Update(True)
        self.window.Element("latDeg").Update(
            abs(latdeg) if type(latdeg) == int else "")
        self.window.Element("latMin").Update(
            abs(latmin) if type(latmin) == int else "")
        self.window.Element("latSec").Update(
            abs(latsec) if type(latsec) == float else "")

        if londeg == "" or londeg >= 0:
            self.window.Element("East").Update(True)
        else:
            self.window.Element("West").Update(True)
        self.window.Element("lonDeg").Update(
            abs(londeg) if type(londeg) == int else "")
        self.window.Element("lonMin").Update(
            abs(lonmin) if type(lonmin) == int else "")
        self.window.Element("lonSec").Update(
            abs(lonsec) if type(lonsec) == float else "")

        if elevation is not None:
            elevation = round(elevation)
        else:
            elevation = ""

        self.window.Element("elevFeet").Update(elevation)
        self.window.Element("elevMeters").Update(
            round(elevation/3.281) if type(elevation) == int else "")
        if aircraft is not None:
            self.window.Element(aircraft).Update(value=True)

        if update_mgrs:
            self.window.Element("mgrs").Update(mgrs_str)
        self.window.Refresh()

        if type(name) == str:
            self.window.Element("msnName").Update(name)
        else:
            self.window.Element("msnName").Update("")

        if waypoint_type is not None:
            self.select_wp_type(waypoint_type)

        if station is not None:
            self.set_sequence_station_selector('station', station=station)

    def update_waypoints_list(self, set_to_first=False):
        values = list()
        self.profile.update_waypoint_numbers()

        for wp in sorted(self.profile.waypoints,
                         key=lambda waypoint: waypoint.wp_type if waypoint.wp_type != "MSN" else str(waypoint.station)):
            namestr = str(wp)

            if not self.editor.driver.validate_waypoint(wp):
                namestr = strike(namestr)

            values.append(namestr)

        if set_to_first:
            self.window.Element('activesList').Update(values=values, set_to_index=0)
        else:
            self.window.Element('activesList').Update(values=values)
        self.window.Element("aircraftSelector").Update(value=self.aircraft_name[self.aircraft.index(self.profile.aircraft)])

    def disable_coords_input(self):
        for element_name in\
                ("latDeg", "latMin", "latSec", "lonDeg", "lonMin", "lonSec", "mgrs", "elevFeet", "elevMeters", "Send"):
            self.window.Element(element_name).Update(disabled=True)

    def enable_coords_input(self):
        for element_name in\
                ("latDeg", "latMin", "latSec", "lonDeg", "lonMin", "lonSec", "mgrs", "elevFeet", "elevMeters", "Send"):
            self.window.Element(element_name).Update(disabled=False)

    def filter_preset_waypoints_dropdown(self):
        text = self.values["baseSelector"]
        self.window.Element("baseSelector").\
            Update(values=[""] + sorted([base.name for _, base in self.editor.default_bases.items() if
                                  text.lower() in base.name.lower()]),
                   set_to_index=0)

    def filter_profile_dropdown(self):
        text = self.values["profileSelector"]
        self.window.Element("profileSelector").\
            Update(values=[""] + sorted([profile.name for profile in Profile.list_all() if
                           text.lower() in profile.name.lower()]), set_to_index=0)

    def next_station(self, station):
        station_list = [3, 7, 2, 8]
        station_idx = station_list.index(station)
        self.set_sequence_station_selector('station', station_list[station_idx - 1])

    def add_waypoint(self, position, elevation, name=None):
        if name is None:
            name = str()

        try:
            if self.selected_wp_type == "MSN":
                station = int(self.values.get("sequence", 0))
                number = len(self.profile.stations_dict.get(station, list()))+1
                wp = MSN(position=position, elevation=int(elevation) or 0, name=name,
                         station=station, number=number)
                self.next_station(station)

            else:
                sequence = self.values["sequence"]
                if sequence == "None":
                    sequence = 0
                else:
                    sequence = int(sequence)

                if sequence and len(self.profile.get_sequence(sequence)) >= 15:
                    return False

                wp = Waypoint(position, elevation=int(elevation or 0),
                              name=name, sequence=sequence, wp_type=self.selected_wp_type,
                              number=len(self.profile.waypoints_of_type(self.selected_wp_type))+1)

                if sequence not in self.profile.sequences:
                    self.profile.sequences.append(sequence)

            self.profile.waypoints.append(wp)
            self.update_waypoints_list()
        except ValueError:
            PyGUI.Popup("Error: missing data or invalid data format")

        return True

    def export_to_string(self):
        dump = str(self.profile)
        encoded = json_zip(dump)
        pyperclip.copy(encoded)
        PyGUI.Popup('Encoded string copied to clipboard, paste away!')

    def import_from_string(self):
        # Load the encoded string from the clipboard
        encoded = pyperclip.paste()
        try:
            decoded = json_unzip(encoded)
            self.profile = Profile.from_string(decoded)
            self.profile.profilename = ""
            self.logger.debug(self.profile.to_dict())
            self.editor.set_driver(self.profile.aircraft)
            self.update_waypoints_list(set_to_first=True)
            self.window.Element("profileSelector").Update(set_to_index=0)
            PyGUI.Popup('Loaded waypoint data from encoded string successfully')
        except Exception as e:
            self.logger.error(e, exc_info=True)
            PyGUI.Popup('Failed to parse profile from string')

    def import_NS430(self, text):
        # Load NS430 dat
        lines = list(text.split('\n'))
        for i in range(len(lines)):
            fields = list(lines[i].strip().split(";"))
            if len(fields) == 4 and fields[0] == "FIX":
                self.logger.info("NS430: " + lines[i])
                try:
                    position = LatLon(Latitude(degree=fields[2]),
                                      Longitude(degree=fields[1]))
                    self.add_waypoint(position, 0, fields[3])
                except Exception as e:
                    self.logger.error(e, exc_info=True)
                    PyGUI.Popup('Data error importing NS430 fixes')

    def load_new_profile(self):
        self.profile = Profile('')

    def add_parsed_coords(self):
        position = None
        name = self.window.Element("msnName").Get()
        try:
            captured_coords = capture_map_coords(self)
            position, elevation = parse_map_coords_string(self, captured_coords)
            self.logger.debug("Parsed text as coords succesfully: " + str(position))
            winsound.PlaySound(UX_SND_SUCCESS, flags=winsound.SND_FILENAME)
        except (IndexError, ValueError, TypeError):
            self.logger.error("Failed to parse captured text", exc_info=True)
            winsound.PlaySound(UX_SND_ERROR, flags=winsound.SND_FILENAME)
        finally:
            if not self.quick_capture:
                self.stop_capture()
            if position is not None:
                self.update_position(position, elevation, name=name, update_mgrs=True)
                self.update_altitude_elements("meters")
                self.window.Element('capture_status').Update("Status: Captured")
                if self.quick_capture:
                    added = self.add_waypoint(position, elevation, name=name)
                    if not added:
                        self.stop_capture()

    def add_camera_coords(self):
        UDP_IP = "127.0.0.1"
        UDP_PORT = 42069
        BUFFER_SIZE = 65508
        data = None
        name = self.window.Element("msnName").Get()

        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) # UDP
            s.bind((UDP_IP, UDP_PORT))
            s.settimeout(2.0)
            data, addr = s.recvfrom(BUFFER_SIZE)
            self.logger.info("Received data from socket: %s" % data)
            winsound.PlaySound(UX_SND_SUCCESS, flags=winsound.SND_FILENAME)
            s.close()
        except Exception as e:
            s.close()
            self.logger.error("Failed to connect socket: %s" % e)
            self.window.Element('capture_status').Update("Status: Failed to connect")
            winsound.PlaySound(UX_SND_ERROR, flags=winsound.SND_FILENAME)
        finally:
            if data:
                wpdata = json.loads(data.decode('utf8'))
                coords = wpdata.get('coords')
                position = LatLon(Latitude(degree=coords.get('lat')),
                                  Longitude(degree=coords.get('long')))
                elevation = float(wpdata.get('elev')) * 3.281

                if position is not None:
                    self.logger.info("Waypoint data: " + str(position) + " " + str(elevation))
                    self.update_position(position, elevation, name=name, update_mgrs=True)
                    self.update_altitude_elements("meters")
                    self.window.Element('capture_status').Update("Status: Captured")
                    added = self.add_waypoint(position, elevation, name=name)
                    if not added:
                        self.stop_capture()

    def toggle_quick_capture(self):
        if self.values:
            winsound.PlaySound(UX_SND_SUCCESS, flags=winsound.SND_FILENAME)
            if self.capturing:
                self.stop_capture()
            else:
                self.quick_capture = True
                self.start_capture()

    def toggle_camera_capture(self):
        if self.values:
            winsound.PlaySound(UX_SND_SUCCESS, flags=winsound.SND_FILENAME)
            if self.capturing:
                self.stop_capture()
            else:
                self.start_camera_capture()

    def start_capture(self):
        self.disable_coords_input()
        if self.quick_capture:
            self.window.Element('quick_capture').Update(text="Stop capturing")
            self.window.Element('capture').Update(disabled=True)
        else:
            self.window.Element('capture').Update(text="Stop capturing")
            self.window.Element('quick_capture').Update(disabled=True)
        self.window.Element('camera_capture').Update(disabled=True)
        self.window.Element('capture_status').Update("Status: Capturing...")
        self.window.Refresh()
        keyboard.add_hotkey(self.capture_key, self.add_parsed_coords, timeout=1)
        self.capturing = True

    def stop_capture(self):
        try:
            keyboard.remove_hotkey(self.capture_key)
        except KeyError:
            pass

        self.enable_coords_input()
        self.window.Element('capture').Update(text="Capture Coordinates")
        self.window.Element('quick_capture').Update(text="Capture To Profile")
        self.window.Element('camera_capture').Update(text="Capture F10/F11 View")
        self.window.Element('quick_capture').Update(disabled=self.capture_button_disabled)
        self.window.Element('capture').Update(disabled=self.capture_button_disabled)
        self.window.Element('camera_capture').Update(disabled=(not self.enable_the_way))
        self.window.Element('capture_status').Update("Status: Not capturing")
        self.capturing = False
        self.quick_capture = False

    def start_camera_capture(self):
        self.disable_coords_input()
        self.window.Element('camera_capture').Update(text="Stop capturing")
        self.window.Element('quick_capture').Update(disabled=True)
        self.window.Element('capture').Update(disabled=True)
        self.window.Element('camera_capture').Update(disabled=False)
        self.window.Element('capture_status').Update("Status: Capturing...")
        self.window.Refresh()
        keyboard.add_hotkey(self.capture_key, self.add_camera_coords, timeout=1)
        self.capturing = True

    def update_altitude_elements(self, elevation_unit):
        if elevation_unit == "feet":
            elevation = self.window.Element("elevMeters").Get()
            try:
                if elevation:
                    self.window.Element("elevFeet").Update(
                        round(int(elevation)*3.281))
                else:
                    self.window.Element("elevFeet").Update("")
            except ValueError:
                pass
        elif elevation_unit == "meters":
            elevation = self.window.Element("elevFeet").Get()
            try:
                if elevation:
                    self.window.Element("elevMeters").Update(
                        round(int(elevation)/3.281))
                else:
                    self.window.Element("elevMeters").Update("")
            except ValueError:
                pass

    def validate_coords(self):
        # Make lat/lon negative for S/W before converting position
        lat_dir = ""
        lon_dir = ""
        if self.window.Element("South").Get():
            lat_dir = "-"
        if self.window.Element("West").Get():
            lon_dir = "-"

        lat_deg = lat_dir + self.window.Element("latDeg").Get()
        lat_min = lat_dir + self.window.Element("latMin").Get()
        lat_sec = lat_dir + self.window.Element("latSec").Get()

        lon_deg = lon_dir + self.window.Element("lonDeg").Get()
        lon_min = lon_dir + self.window.Element("lonMin").Get()
        lon_sec = lon_dir + self.window.Element("lonSec").Get()

        try:
            position = LatLon(Latitude(degree=lat_deg, minute=lat_min, second=lat_sec),
                              Longitude(degree=lon_deg, minute=lon_min, second=lon_sec))

            try:
                elevation = int(self.window.Element("elevFeet").Get())
            except:
                elevation = 0

            name = self.window.Element("msnName").Get()
            return position, elevation, name
        except ValueError as e:
            self.logger.error(f"Failed to validate coords: {e}")
            return None, None, None

    def write_profile(self):
        profiles = self.get_profile_names()
        overwrite = "OK"
        name = PyGUI.PopupGetText(
            "Enter profile name", "Saving profile")
        if name in profiles:
            overwrite = PyGUI.PopupOKCancel("Profile " + name + " already exists, overwrite?")
        if name and overwrite == "OK":
            self.profile.save(name)
            self.update_profiles_list(name)

    def update_profiles_list(self, name):
        profiles = sorted(self.get_profile_names())
        self.window.Element("profileSelector").Update(values=[""] + profiles,
                                                      set_to_index=profiles.index(name) + 1)

    def select_wp_type(self, wp_type):
        self.selected_wp_type = wp_type

        if wp_type == "WP":
            self.set_sequence_station_selector("sequence")
        elif wp_type == "MSN":
            self.set_sequence_station_selector("station")
        else:
            self.set_sequence_station_selector(None)

        self.window.Element("wpType").Update(value=wp_type)

    def find_selected_waypoint(self):
        valuestr = unstrike(self.values['activesList'][0])
        for wp in self.profile.waypoints:
            if str(wp) == valuestr:
                return wp

    def remove_selected_waypoint(self):
        valuestr = unstrike(self.values['activesList'][0])
        for wp in self.profile.waypoints:
            if str(wp) == valuestr:
                self.profile.waypoints.remove(wp)

    def enter_coords_to_aircraft(self):
        self.window.Element('Send').Update(disabled=True)
        self.editor.enter_all(self.profile, self.enter_method)
        self.window.Element('Send').Update(disabled=False)

    def run(self):
        self.window.Element("aircraftSelector").Update(value=self.aircraft_name[self.aircraft.index(self.default_aircraft)])
        while True:
            event, self.values = self.window.Read()
            self.logger.debug(f"Event: {event}")
            self.logger.debug(f"Values: {self.values}")

            if event is None or event == 'Exit':
                self.logger.info("Exiting...")
                break

            elif event == "Settings":
                first_time_setup(self.editor.settings)
                self.default_aircraft = try_get_setting(self.editor.settings, "default_aircraft", "hornet")
                self.enter_method = try_get_setting(self.editor.settings, "enter_method", "DCS-BIOS")

            elif event == "Run Target Jar":
                if os.path.exists('.\Target-jar-with-dependencies.jar'):
                    subprocess.Popen(['java', '-jar', '.\Target-jar-with-dependencies.jar'], shell=True)

            elif event == "Copy as String to clipboard":
                self.export_to_string()

            elif event == "Paste as String from clipboard":
                self.import_from_string()

            elif event == "Import NS430 from clipboard":
                importdata = pyperclip.paste()
                self.import_NS430(importdata)

            elif event == "Import NS430 from file":
                filename = PyGUI.PopupGetFile(
                    "Enter file name", "Importing NS430 Data")
                if filename is None:
                    continue

                with open(filename, "r") as f:
                    importdata = f.read()
                self.import_NS430(importdata)

            elif event == "Add":
                position, elevation, name = self.validate_coords()
                if position is not None:
                    self.add_waypoint(position, elevation, name)

            elif event == "Update":
                if self.values['activesList']:
                    waypoint = self.find_selected_waypoint()
                    position, elevation, name = self.validate_coords()
                    if position is not None:
                        waypoint.position = position
                        waypoint.elevation = elevation
                        waypoint.name = name
                        self.update_waypoints_list()

            elif event == "Remove":
                if self.values['activesList']:
                    self.remove_selected_waypoint()
                    self.update_waypoints_list()

            elif event == "Send":
                self.enter_coords_to_aircraft()

            elif event == "activesList":
                if self.values['activesList']:
                    waypoint = self.find_selected_waypoint()
                    if waypoint.wp_type == "MSN":
                        station = waypoint.station
                    else:
                        station = None
                    self.update_position(waypoint.position, waypoint.elevation, waypoint.name,
                                         waypoint_type=waypoint.wp_type, station=station)

            elif event == "Save Profile":
                if self.profile.waypoints:
                    name = self.profile.profilename
                    if name:
                        self.profile.save(name)
                        self.update_profiles_list(name)
                    else:
                        self.write_profile()

            elif event == "Save Profile As...":
                if self.profile.waypoints:
                    self.write_profile()

            elif event == "Delete Profile":
                if not self.profile.profilename:
                    continue
                confirm_delete = PyGUI.PopupOKCancel(
                                "Confirm delete " + self.profile.profilename + "?")
                if confirm_delete == "OK":
                    Profile.delete(self.profile.profilename)
                    profiles = sorted(self.get_profile_names())
                    self.window.Element("profileSelector").Update(
                        values=[""] + profiles)
                    self.load_new_profile()
                    self.update_waypoints_list()
                    self.update_position()

            elif event == "profileSelector":
                try:
                    profile_name = self.values['profileSelector']
                    if profile_name != '':
                        self.profile = Profile.load(profile_name)
                    else:
                        self.profile = Profile('', aircraft=self.profile.aircraft)
                    self.editor.set_driver(self.profile.aircraft)
                    self.update_waypoints_list()

                except DoesNotExist:
                    PyGUI.Popup("Profile not found")

            elif event == "Save as Encoded file":
                filename = PyGUI.PopupGetFile("Enter file name", "Exporting profile", default_extension=".json",
                                              save_as=True, file_types=(("JSON File", "*.json"),))

                if filename is None:
                    continue

                with open(filename, "w+") as f:
                    f.write(str(self.profile))

            elif event == "Copy plain Text to clipboard":
                profile_string = self.profile.to_readable_string()
                pyperclip.copy(profile_string)
                PyGUI.Popup("Profile copied as plain text to clipboard")

            elif event == "Load from Encoded file":
                filename = PyGUI.PopupGetFile(
                    "Enter file name", "Importing profile")

                if filename is None:
                    continue

                with open(filename, "r") as f:
                    self.profile = Profile.from_string(f.read())
                self.editor.set_driver(self.profile.aircraft)
                self.update_waypoints_list()

                if self.profile.profilename:
                    self.update_profiles_list(self.profile.profilename)

            elif event == "capture":
                if not self.capturing:
                    self.start_capture()
                else:
                    self.stop_capture()

            elif event == "quick_capture":
                if not self.capturing:
                    self.quick_capture = True
                    self.start_capture()
                else:
                    self.stop_capture()

            elif event == "camera_capture":
                if not self.capturing:
                    self.start_camera_capture()
                else:
                    self.stop_capture()

            elif event == "baseSelector":
                base = self.editor.default_bases.get(
                    self.values['baseSelector'])

                if base is not None:
                    self.update_position(
                        base.position, base.elevation, base.name)

            elif event == "regionSelector":
                if self.values[event]:
                    load_base_file(self.editor.base_files[self.values[event]], self.editor.default_bases)
                else:
                    generate_default_bases()

                self.window.Element("baseSelector").\
                    Update(values=[""] + sorted(self.editor.default_bases),
                           set_to_index=0)

            elif event == "wpType":
                self.select_wp_type(self.values.get("wpType"))

            elif event == "elevFeet":
                self.update_altitude_elements("meters")

            elif event == "elevMeters":
                self.update_altitude_elements("feet")

            elif event in ("latDeg", "latMin", "latSec", "lonDeg", "lonMin", "lonSec",
                           "North", "South", "East", "West"):
                position, _, _ = self.validate_coords()

                if position is not None:
                    m = mgrs.encode(mgrs.LLtoUTM(
                        position.lat.decimal_degree, position.lon.decimal_degree), 5)
                    self.window.Element("mgrs").Update(m)

            elif event == "mgrs":
                mgrs_string = self.window.Element("mgrs").Get().upper()
                try:
                    elevation = int(self.window.Element("elevFeet").Get())
                except:
                    elevation = 0
                if mgrs_string:
                    try:
                        decoded_mgrs = mgrs.UTMtoLL(mgrs.decode(mgrs_string.replace(" ", "")))
                        position = LatLon(Latitude(degree=decoded_mgrs["lat"]), Longitude(
                            degree=decoded_mgrs["lon"]))
                        self.update_position(position, elevation, 
                                                name=self.window.Element("msnName").Get(), 
                                                update_mgrs=False)
                    except (TypeError, ValueError, UnboundLocalError) as e:
                        self.logger.error(f"Failed to decode MGRS: {e}")

            elif event == "aircraftSelector":
                selected = self.aircraft[self.aircraft_name.index(self.values.get("aircraftSelector"))]
                self.profile.aircraft = selected
                self.editor.set_driver(selected)
                self.update_waypoints_list()

            elif event == "presetFilter":
                self.filter_preset_waypoints_dropdown()

            elif event == "profileFilter":
                self.filter_profile_dropdown()

            elif event == 'About':
                # Define the layout for the information popup window
                text = f"DCS Waypoint Editor {self.software_version}"
                gpltext = "This program is free software; you can redistribute it and/or \n"\
                          "modify it under the terms of the GNU General Public License as \n"\
                          "published by the Free Software Foundation; either version 3 of \n"\
                          "the License, or at your option any later version. \n\n"\
                          "This program is distributed in the hope that it will be useful, but \n"\
                          "WITHOUT ANY WARRANTY; without even the implied warranty \n"\
                          "of MERCHANTABILITY or FITNESS FOR A PARTICULAR \n"\
                          "PURPOSE. See the GNU General Public License for more details. \n\n"\
                          "You should have received a copy of the GNU General Public License\n"\
                          "along with this program. If not, see <https://www.gnu.org/licenses/>."
                url = 'https://github.com/atcz/DCSWaypointEditor'
                layout = [
                    [PyGUI.Column([
                        [PyGUI.Text(f"{' '*10}{text}", justification='center')],
                        [PyGUI.Text(url, enable_events=True, text_color='blue', key='-LINK-')]
                    ], vertical_alignment='center', justification='center')],
                [PyGUI.Frame("GNU General Public License", [
                    [PyGUI.Text(gpltext, pad=(40,(10,20)))],
                    ])
                ],
                    [PyGUI.Column([
                        [PyGUI.Button('OK', size=(10, 1), pad=(10, 20), bind_return_key=True)]
                    ], vertical_alignment='center', justification='center')]
                ]

                # Create the window
                window = PyGUI.Window('Information', layout, finalize=True, modal=True)

                # Event loop
                while True:
                    event, _ = window.read()
                    if event == PyGUI.WINDOW_CLOSED or event == 'OK':
                        break
                    elif event == '-LINK-':
                        webbrowser.open(url)
                        break
                # Close the window
                window.close()

        self.close()

    def close(self):
        try:
            keyboard.remove_hotkey(self.capture_key)
        except KeyError:
            pass

        self.window.Close()
        self.editor.stop()
