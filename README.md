# DCS Waypoint Editor

Simple configurable script to input preplanned missions and waypoints coordinates into DCS aircraft. 

Currently supported aircraft:

* F/A-18C
* AV-8B
* M-2000C
* F-14A/B
* A-10C
* F-16C
* AH-64D Pilot
* AH-64D CPG
* Ka-50

## Installation

1. Download and install [Google Tesseract](https://github.com/UB-Mannheim/tesseract/wiki)
2. Optional (Recommended) - Download and install [DCSTheWay](https://github.com/aronCiucu/DCSTheway)
3. Unzip the contents of DCS-Waypoint-Editor.zip to a folder
4. Run `dcs_wp_editor.exe` and perform the first time setup.

## How It Works

DCS Waypoint Editor uses a screen capture to search for the map coordinates in the top left corner of the F10 map using Tesseract
OCR. Any screen overlay or screen scaling that obscures or modifies the captured image will result in a "No matching pattern"
error. Capturing using `DCSTheWay` (`Capture F10/F11 View`) will capture coordinates directly from DCS without using OCR. 

## Usage

Waypoints and JDAM/SLAM preplanned missions can be added by either manually entering a set of coordinates or by one of the
coordinate capture methods. When capturing from `DCSTheWay`, coordinates are captured from the current camera view. From the
F10 map, it captures the coordinates of the center of the map. A target dot in the center of the map can be displayed using
the included Target-jar-with-dependencies.jar which requires Java JRE. `DCSTheWay` can not be running when using F10/F11 
View capture.

#### Manual coordinates entry

1. Choose a waypoint type (WP = regular waypoint, MSN = JDAM/SLAM preplanned mission)

2. Enter the latitude and longitude. Decimal seconds are supported.

3. Enter the elevation in feet (optional for regular waypoints, mandatory for JDAM/SLAM preplanned missions)

4. (Optional) Choose a sequence to assign the waypoint to.

5. (Optional) Assign a name to the waypoint.

6. Click `Add` to add the waypoint to the list of active waypoints

#### F10 map captured coordinates entry

1. Make sure your F10 map is in [DD MM SS.ss](https://i.imgur.com/9GIU7pJ.png) or [MGRS](https://i.imgur.com/T7lBvlx.png) coordinate format.
 You may cycle coordinate formats with `LAlt+Y`.

2. Click `Capture Coordinates` or `Capture To Profile`

3. In the DCS F10 map, hover your mouse over your desired position

4. Press the key you bound to F10 map capture during first time setup (default is `LCtrl+T`). The results will be indicated
in the capture status textbox.

5. (Optional) Assign a name to the waypoint.

6. Click `Add` to add the waypoint to the list of active waypoints

#### F10 map quick capture

`Capture To Profile` and `Capture F10/F11 View` work in a similar way to regular coordinates capturing, except it will automatically
add a waypoint  at the desired position every time the map capture keybind is pressed.  `Capture To Profile` and `Capture F10/F11 View`
can be toggled on/off with a hotkey (default is `LCtrl+LShift+T` and `LCtrl+LShift+U`).

#### Preset coordinates

You may select a position from a list of preset coordinates. Coordinates for all Caucasus, Persian Gulf, Marianas, Nevada and Syria airfields
and BlueFlag FARPS are included.

#### Hornet JDAM/SLAM preplanned missions

Hornet JDAM/SLAM preplanned missions work in a similar way to waypoints, however, you **must** select the correct station
for the mission to be assigned using the station selector.  Aircraft entry does not skip stations, and available stations
will be entered in order 8-2-7-3. Missions for different weapons (JSA, J-84, J-109, SLMR, etc.) must be entered separately.

#### Entering a list of waypoints into your aircraft

An optional hotkey can be assigned to enter coordinates into the aircraft.  This is done during initial setup
of the application.

##### F/A-18C

1. Make sure the main HSI page is on the AMPCD (bottom screen) if you are entering waypoints. HSI Precise mode is selected automatically
and must not be turned on in advance.
 
2. If you are entering JDAM/SLAM preplanned missions, make sure to select the MSN preplanned missions page on the left DDI.

![pages](https://i.imgur.com/Nxr9qKX.png)

3. With a list of active waypoints and/or JDAM/SLAM preplanned missions, click `Send To Aircraft`

4. Tab back into DCS and let it enter everything

##### AV-8B

1. Make sure the main EHSD page is on the left AMPCD (left screen).

2. With a list of active waypoints, click `Send To Aircraft`

3. Tab back into DCS and let it enter everything

##### All Other Aircraft

1. With a list of active waypoints, click `Send To Aircraft`

2. Tab back into DCS and let it enter everything

#### Profile saving

You may save your current list of waypoints as a profile and then load it later. Selecting "Save Profile" with a profile active
will overwrite it with the current list.

#### Export to file

If you wish to share your current profile, select `Save as Encoded file` and give it a descriptive name.

#### Import from file

Profiles may be imported from a file that was previously exported by selecting `Load from Encoded file`.

#### Import from NS430

 Waypoint data can be imported from an NS430 data file by selecting `Import NS430 from clipboard` or `Import NS430 from file`.

#### Creating your own preset locations

You may add more preset locations by adding more JSON formatted files in the data folder,
following the format in `pg.json` and `cauc.json`.

#### Exporting to encoded string

Support for exporting current profile to an encoded string has been implemented to allow for quick sharing
of waypoint and mission data to other people.  Once you have created a mission, select `Copy as String to clipboard`
from the menu.  This will copy an encoded string to your clipboard to share with other users.

#### Importing from encoded string

Once another user has sent their encoded string to yourself, just copy the string to your clipboard (default `LCtrl+C`)
and select `Paste as String from clipboard`.  If successful, their mission data should be imported into
a new profile and a pop-up should appear letting you know import was successful.

## Known issues

* Attempting to enter sequence #2 or #3 without sequence #1 will not work.

## About DCS-BIOS
DCS-BIOS is redistributed under GPLv3 license.

DCS-BIOS: https://github.com/DCSFlightpanels/dcs-bios

## Other credits
[PyMGRS](https://github.com/aydink/pymgrs) by aydink

DCSTheWay: https://github.com/aronCiucu/DCSTheWay
