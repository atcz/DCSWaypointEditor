from PIL import ImageEnhance, ImageOps
from desktopmagic.screengrab_win32 import getDisplaysAsImages
from LatLon23 import LatLon, Longitude, Latitude, string2latlon
import src.pymgrs as mgrs
import pytesseract
import os
import cv2
import numpy
import re
import datetime

def text_from_image(self, cropped, name):
    cropped = cropped.resize((cropped.width * 3, cropped.height * 3)).convert("L")
    enhancer = ImageEnhance.Contrast(cropped)
    enhanced = enhancer.enhance(3)
    inverted = ImageOps.invert(enhanced)

    if self.save_debug_images == "true":
        cropped.save(self.debug_dirname + f"/{name}_image.png")
        enhanced.save(self.debug_dirname + f"/{name}_image_enhanced.png")
        inverted.save(self.debug_dirname + f"/{name}_image_inverted.png")

    captured_text = pytesseract.image_to_string(inverted).rstrip('\n\.\,')

    self.logger.debug(f"Raw captured text: {captured_text}")
    return captured_text

def capture_map_coords(self):
    self.logger.debug("Attempting to capture map coords")
    gui_mult = 2 if self.scaled_dcs_gui else 1

    dt = datetime.datetime.now()
    self.debug_dirname = "debug_images/" + dt.strftime("%Y-%m-%d-%H-%M-%S")

    if self.save_debug_images == "true":
        if not os.path.exists("debug_images"):
            os.mkdir("debug_images")
        os.mkdir(self.debug_dirname)

    map_image       = cv2.imread("data/map.bin")
    arrow_image     = cv2.imread("data/arrow.bin")
    alt_image       = cv2.imread("data/alt.bin")
    country_image   = cv2.imread("data/country.bin")
    callsign_image  = cv2.imread("data/callsign.bin")

    for display_number, image in enumerate(getDisplaysAsImages(), 1):
        self.logger.debug("Looking for map on screen " + str(display_number))

        if self.save_debug_images == "true":
            image.save(self.debug_dirname + "/screenshot-"+str(display_number)+".png")

        screen_image = cv2.cvtColor(numpy.array(image), cv2.COLOR_RGB2BGR)  # convert it to OpenCV format

        search_result = cv2.matchTemplate(screen_image, map_image, cv2.TM_CCOEFF_NORMED)  # search for the "MAP" text in the screenshot
        # matchTemplate returns a new greyscale image where the brightness of each pixel corresponds to how good a match there was at that point
        # so now we search for the 'whitest' pixel
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(search_result)
        self.logger.debug("MAP - Minval: " + str(min_val) + " Maxval: " + str(max_val) + " Minloc: " + str(min_loc) + " Maxloc: " + str(max_loc))
        start_x = max_loc[0] + map_image.shape[1]
        start_y = max_loc[1]

        if max_val > 0.9:  # better than a 90% match means we are on to something
            search_result = cv2.matchTemplate(screen_image, arrow_image, cv2.TM_CCOEFF_NORMED)  # now we search for the arrow icon
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(search_result)
            self.logger.debug("Arrow - Minval: " + str(min_val) + " Maxval: " + str(max_val) + " Minloc: " + str(min_loc) + " Maxloc: " + str(max_loc))

            end_x = max_loc[0]
            end_y = max_loc[1] + map_image.shape[0]

            self.logger.debug("Capturing " + str(start_x) + "x" + str(start_y) + " to " + str(end_x) + "x" + str(end_y) )

            lat_lon_image = image.crop([start_x, start_y, end_x, end_y])
            captured_map_coords = text_from_image(self, lat_lon_image, "lat_lon")

            # now search for selected object data
            search_result = cv2.matchTemplate(screen_image, alt_image, cv2.TM_CCOEFF_NORMED) # Search for ALT (object selected)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(search_result)
            self.logger.debug("ALT - Minval: " + str(min_val) + " Maxval: " + str(max_val) + " Minloc: " + str(min_loc) + " Maxloc: " + str(max_loc))
            start_x = max_loc[0] + alt_image.shape[1]
            start_y = max_loc[1]

            if max_val > 0.9:  # found the object data box, so get the altitude and coords
                search_result = cv2.matchTemplate(screen_image, country_image, cv2.TM_CCOEFF_NORMED)  # search for COUNTRY
                min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(search_result)
                self.logger.debug("COUNTRY - Minval: " + str(min_val) + " Maxval: " + str(max_val) + " Minloc: " + str(min_loc) + " Maxloc: " + str(max_loc))

                end_x = max_loc[0]
                end_y = max_loc[1] + country_image.shape[0]

                self.logger.debug("Capturing " + str(start_x) + "x" + str(start_y) + " to " + str(end_x) + "x" + str(end_y) )

                object_alt_image = image.crop([start_x, start_y, end_x, end_y])
                captured_object_alt = text_from_image(self, object_alt_image, "object_alt") or 0

                search_result = cv2.matchTemplate(screen_image, callsign_image, cv2.TM_CCOEFF_NORMED)  # search for CALLSIGN
                min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(search_result)
                self.logger.debug("CALLSIGN - Minval: " + str(min_val) + " Maxval: " + str(max_val) + " Minloc: " + str(min_loc) + " Maxloc: " + str(max_loc))

                start_x = start_x - alt_image.shape[1]
                start_y = max_loc[1]
                end_x = max_loc[0]
                end_y = max_loc[1] + callsign_image.shape[0]

                self.logger.debug("Capturing " + str(start_x) + "x" + str(start_y) + " to " + str(end_x) + "x" + str(end_y) )

                object_lat_lon_image = image.crop([start_x, start_y, end_x, end_y])
                captured_object_coords = text_from_image(self, object_lat_lon_image, "object_lat_lon")
                if captured_map_coords[-2:] == "ft":
                    captured_map_coords = f"{captured_object_coords}, {captured_object_alt} ft"
                else:
                    captured_map_coords = f"{captured_object_coords}, {captured_object_alt} m"

            return captured_map_coords

    self.logger.debug("Raise exception (could not find the map anywhere i guess)")
    self.window.Element('capture_status').Update("Status: F10 map not found")
    raise ValueError("F10 map not found")

def parse_map_coords_string(self, coords_string):
    coords_string = coords_string.upper().replace(")", "J").replace("]", "J").replace("}", "J").replace("£", "E")
    # "X-00199287 Z+00523070, 0 ft"   Not sure how to convert this yet

    # "37 T FJ 36255 11628, 5300 ft"  MGRS
    res = re.search("(\d+\s?[a-zA-Z\)]\s?[a-zA-Z\)][a-zA-Z\)] \d+ \d+),+ (-?\d+) (FT|M)$", coords_string)
    if res is not None:
        mgrs_string = res.group(1).replace(" ", "")
        decoded_mgrs = mgrs.UTMtoLL(mgrs.decode(mgrs_string))
        position = LatLon(Latitude(degree=decoded_mgrs["lat"]), Longitude(
            degree=decoded_mgrs["lon"]))
        elevation = max(0, float(res.group(2)))

        if res.group(3) == "M":
            elevation = elevation * 3.281

        self.logger.debug(f"MGRS input found: {mgrs_string} {decoded_mgrs} {elevation}")
        return position, elevation

    # "N43°10.244 E40°40.204, 477 ft"  Degrees and decimal minutes
    res = re.search("([NS])(\d+)[°'](\d+\.\d+) ([EW])(\d+)[°'](\d+\.\d+),+ (-?\d+) (FT|M)$", coords_string)
    if res is not None:
        lat_str = res.group(2) + " " + res.group(3) + " " + res.group(1)
        lon_str = res.group(5) + " " + res.group(6) + " " + res.group(4)
        position = string2latlon(lat_str, lon_str, "d% %M% %H")
        elevation = max(0, float(res.group(7)))

        if res.group(8) == "M":
            elevation = elevation * 3.281

        self.logger.debug(f"DD MM.MMM input found: {lat_str} {lon_str} {elevation}")
        return position, elevation

    # "N42-43-17.55 E40-38-21.69, 0 ft" Degrees, minutes and decimal seconds
    res = re.search("([NS])(\d+)-(\d+)-(\d+\.\d+) ([EW])(\d+)-(\d+)-(\d+\.\d+),+ (-?\d+) (FT|M)$", coords_string)
    if res is not None:
        lat_str = res.group(2) + " " + res.group(3) + " " + res.group(4) + " " + res.group(1)
        lon_str = res.group(6) + " " + res.group(7) + " " + res.group(8) + " " + res.group(5)
        position = string2latlon(lat_str, lon_str, "d% %m% %S% %H")
        elevation = max(0, float(res.group(9)))

        if res.group(10) == "M":
            elevation = elevation * 3.281

        self.logger.debug(f"DD MM SS.SS input found: {lat_str} {lon_str} {elevation}")
        return position, elevation

    # "43°34'37"N 29°11'18"E, 0 ft" Degrees minutes and seconds
    res = re.search("(\d+)[°'](\d+)[°'](\d+)[°'\"\*]([NS]) (\d+)[°'](\d+)[°'](\d+)[°'\"\*]([EW]),+ (-?\d+) (FT|M)$", coords_string)
    if res is not None:
        lat_str = res.group(1) + " " + res.group(2) + " " + res.group(3) + " " + res.group(4)
        lon_str = res.group(5) + " " + res.group(6) + " " + res.group(7) + " " + res.group(8)
        position = string2latlon(lat_str, lon_str, "d% %m% %S% %H")
        elevation = max(0, float(res.group(9)))

        if res.group(10) == "M":
            elevation = elevation * 3.281

        self.logger.debug(f"DD MM SS input found: {lat_str} {lon_str} {elevation}")
        return position, elevation

    # Could not find any matching text
    self.logger.debug("Text found " + coords_string + " but did not match any known pattern.")
    self.window.Element('capture_status').Update(
        "Status: No matching pattern")
    raise ValueError("No matching pattern")
    return None, None
