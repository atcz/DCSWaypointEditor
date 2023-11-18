import socket
import re
import json
from time import sleep
from configparser import NoOptionError


class DriverException(Exception):
    pass


def latlon_tostring(latlong, decimal_minutes_mode=False, easting_zfill=2, zfill_minutes=2, one_digit_seconds=False, precision=4, dfill=False):

    if not decimal_minutes_mode:
        lat_deg = str(abs(round(latlong.lat.degree)))
        lat_min = str(abs(round(latlong.lat.minute))).zfill(zfill_minutes)
        lat_sec = abs(latlong.lat.second)

        lat_sec_int, lat_sec_dec = divmod(lat_sec, 1)

        lat_sec = str(int(lat_sec_int)).zfill(2)

        if lat_sec_dec:
            lat_sec += "." + str(round(lat_sec_dec, 2))[2:4]

        lon_deg = str(abs(round(latlong.lon.degree))).zfill(easting_zfill)
        lon_min = str(abs(round(latlong.lon.minute))).zfill(zfill_minutes)
        lon_sec = abs(latlong.lon.second)

        lon_sec_int, lon_sec_dec = divmod(lon_sec, 1)

        lon_sec = str(int(lon_sec_int)).zfill(2)

        if lon_sec_dec:
            lon_sec += "." + str(round(lon_sec_dec, 2))[2:4]

        if one_digit_seconds:
            lat_sec = str(round(float(lat_sec)) // 10)
            lon_sec = str(round(float(lon_sec)) // 10)

        return lat_deg + lat_min + lat_sec, lon_deg + lon_min + lon_sec
    else:
        lat_deg = str(abs(round(latlong.lat.degree)))
        lat_min = str(round(latlong.lat.decimal_minute, precision))

        lat_min_split = lat_min.split(".")
        lat_min_split[0] = lat_min_split[0].zfill(zfill_minutes)
        if dfill:
            lat_min_split[1] = lat_min_split[1].ljust(precision, '0')
        lat_min = ".".join(lat_min_split)

        lon_deg = str(abs(round(latlong.lon.degree))).zfill(easting_zfill)
        lon_min = str(round(latlong.lon.decimal_minute, precision))

        lon_min_split = lon_min.split(".")
        lon_min_split[0] = lon_min_split[0].zfill(zfill_minutes)
        if dfill:
            lon_min_split[1] = lon_min_split[1].ljust(precision, '0')
        lon_min = ".".join(lon_min_split)

        return lat_deg + lat_min, lon_deg + lon_min


class Driver:
    def __init__(self, logger, config, host="127.0.0.1", port=7778):
        self.logger = logger
        self.s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.host, self.port = host, port
        self.config = config
        self.limits = dict()
        self.keylist = list()

        try:
            self.short_delay = float(self.config.get("PREFERENCES", "button_release_short_delay"))
            self.medium_delay = float(self.config.get("PREFERENCES", "button_release_medium_delay"))
        except NoOptionError:
            self.short_delay, self.medium_delay = 0.2, 0.5

    def press_with_delay(self, key, delay_after=None, delay_release=None, raw=False):
        if not key:
            return False

        if self.method == "DCS-BIOS":
            if delay_after is None:
                delay_after = self.short_delay

            if delay_release is None:
                delay_release = self.short_delay

            encoded_str = key.encode("utf-8")                                                              
            if not raw:
                sent = self.s.sendto(f"{key} 1\n".encode("utf-8"), (self.host, self.port))
                sleep(delay_release)

                self.s.sendto(f"{key} 0\n".encode("utf-8"), (self.host, self.port))
                strlen = len(encoded_str) + 3
            else:
                sent = self.s.sendto(f"{key}\n".encode("utf-8"), (self.host, self.port))
                strlen = len(encoded_str) + 1

            sleep(delay_after)
            return sent == strlen
        else:
            self.keylist.append(key)
            return True

    def enter_keypress(self, keylist):
        host = "127.0.0.1"
        port = 42070

        commands = list()
        for key in keylist:
            commands.append(self.cmdlist.get(key))
        commandstr = json.dumps(commands) + "\n"
#        self.logger.info(keylist)
#        self.logger.info(commandstr)

        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((host, port))
            s.settimeout(2.0)
            s.send(commandstr.encode('utf-8'))
            s.close()
        except Exception as e:
            s.close()
            self.logger.error("Failed to connect socket: %s" % e)

    def validate_waypoint(self, waypoint):
        try:
            return self.limits[waypoint.wp_type] is None or waypoint.number <= self.limits[waypoint.wp_type]
        except KeyError:
            return False

    def validate_waypoints(self, waypoints):
        for waypoint in waypoints[:]:
            if not self.validate_waypoint(waypoint):
                waypoints.remove(waypoint)
        return sorted(waypoints, key=lambda wp: wp.wp_type)

    def waypoints_by_sequence(self, waypoints):
        wpnumber = 1
        wpsequence = None
        wplist = list()
        for wp in sorted(waypoints, key=lambda waypoint: waypoint.sequence):
            if wp.sequence != wpsequence:
                wpnumber = 1
                wpsequence = wp.sequence
            wp.number = wpnumber
            wplist.append(wp)
            wpnumber += 1
        return wplist

    def stop(self):
        self.s.close()


class HornetDriver(Driver):
    def __init__(self, logger, config):
        super().__init__(logger, config)
        self.limits = dict(WP=None, MSN=6)

    def ufc(self, num, delay_after=None, delay_release=None):
        key = f"UFC_{num}"
        self.press_with_delay(key, delay_after=delay_after,
                              delay_release=delay_release)

    def lmdi(self, pb, delay_after=None, delay_release=None):
        key = f"LEFT_DDI_PB_{pb.zfill(2)}"
        self.press_with_delay(key, delay_after=delay_after,
                              delay_release=delay_release)

    def ampcd(self, pb, delay_after=None, delay_release=None):
        key = f"AMPCD_PB_{pb.zfill(2)}"
        self.press_with_delay(key, delay_after=delay_after,
                              delay_release=delay_release)

    def enter_number(self, number, two_enters=False):
        for num in str(number):
            if num == ".":
                break

            self.ufc(num)

        self.ufc("ENT", delay_release=self.medium_delay)

        i = str(number).find(".")

        if two_enters:
            if i > 0:
                for num in str(number)[str(number).find(".") + 1:]:
                    self.ufc(num)

            self.ufc("ENT", delay_release=self.medium_delay)

    def enter_coords(self, latlong, elev, pp, decimal_minutes_mode=False):
        lat_str, lon_str = latlon_tostring(latlong, decimal_minutes_mode=decimal_minutes_mode)
        self.logger.debug(f"{self.method} - Entering coords string: {lat_str}, {lon_str}")

        if not pp:
            if latlong.lat.degree > 0:
                self.ufc("2", delay_release=self.medium_delay)
            else:
                self.ufc("8", delay_release=self.medium_delay)
            self.enter_number(lat_str, two_enters=True)
            sleep(0.5)

            if latlong.lon.degree > 0:
                self.ufc("6", delay_release=self.medium_delay)
            else:
                self.ufc("4", delay_release=self.medium_delay)
            self.enter_number(lon_str, two_enters=True)

            if elev or elev == 0:
                self.ufc("OS3")
                self.ufc("OS1")
                if elev < 0:
                    self.ufc("0")
                self.enter_number(elev)
        else:
            self.ufc("OS1")
            if latlong.lat.degree > 0:
                self.ufc("2", delay_release=self.medium_delay)
            else:
                self.ufc("8", delay_release=self.medium_delay)
            self.enter_number(lat_str, two_enters=True)

            self.ufc("OS3")
            if latlong.lon.degree > 0:
                self.ufc("6", delay_release=self.medium_delay)
            else:
                self.ufc("4", delay_release=self.medium_delay)
            self.enter_number(lon_str, two_enters=True)

            if elev or elev == 0:
                self.ufc("CLR")
                self.lmdi("14")
                self.ufc("OS4")
                self.ufc("OS3")
                if elev < 0:
                    self.ufc("0")
                self.enter_number(elev)

    def enter_waypoints(self, wps, sequences):
        if not wps:
            return

        self.ampcd("10")
        self.ampcd("19")
        self.ufc("CLR")
        self.ufc("CLR")

        for wp in wps:
            self.logger.info(f"Entering waypoint: {wp}")
            self.ampcd("12")
            self.ampcd("5")
            self.ufc("OS1")
            self.enter_coords(wp.position, wp.elevation, pp=False, decimal_minutes_mode=True)
            self.ufc("CLR")

        for sequencenumber, waypointslist in sequences.items():
            if sequencenumber != 1:
                self.ampcd("15")
                self.ampcd("15")
            else:
                waypointslist = [0] + waypointslist

            self.ampcd("1")

            for waypoint in waypointslist:
                self.ufc("OS4")
                self.enter_number(waypoint)

        self.ufc("CLR")
        self.ufc("CLR")
        self.ampcd("19")
        self.ampcd("10")

    def enter_missions(self, missions):
        def stations_order(x):
            order = [8, 2, 7, 3]
            return order.index(x)

        sorted_stations = list()
        stations = dict()
        for mission in missions:
            station_msn_list = stations.get(mission.station, list())
            station_msn_list.append(mission)
            stations[mission.station] = station_msn_list

        for k in sorted(stations, key=stations_order):
            sorted_stations.append(stations[k])

        for msns in sorted_stations:
            if not msns:
                return

            n = 1
            for msn in msns:
                self.logger.info(f"Entering PP mission: {msn}")
                msn.elevation = max(1, msn.elevation)
                if n > 1:
                    self.lmdi(f"{n + 5}")
                self.lmdi("14")
                self.ufc("OS3")
                self.enter_coords(msn.position, msn.elevation, pp=True)
                self.ufc("CLR")
                self.ufc("CLR")
                n += 1
            if n > 2:
                self.lmdi("6")
            self.lmdi("13")
        self.lmdi("19")

    def enter_all(self, profile):
        self.keylist = []
        self.enter_missions(self.validate_waypoints(profile.msns_as_list))
        sleep(1)
        self.enter_waypoints(self.validate_waypoints(profile.waypoints_as_list), profile.sequences_dict)
        if self.method != "DCS-BIOS":
            self.enter_keypress(self.keylist)


class HarrierDriver(Driver):
    def __init__(self, logger, config):
        super().__init__(logger, config)
        self.limits = dict(WP=None)

    def ufc(self, num, delay_after=None, delay_release=None):
        if num not in ("ENTER", "CLEAR", "DOT", "DASH"):
            key = f"UFC_B{num}"
        else:
            key = f"UFC_{num}"
        self.press_with_delay(key, delay_after=delay_after,
                              delay_release=delay_release)

    def odu(self, num, delay_after=None, delay_release=None):
        key = f"ODU_OPT{num}"
        self.press_with_delay(key, delay_after=delay_after,
                              delay_release=delay_release)

    def lmpcd(self, pb, delay_after=None, delay_release=None):
        key = f"MPCD_L_{pb}"
        self.press_with_delay(key, delay_after=delay_after, delay_release=delay_release)

    def enter_number(self, number, two_enters=False):
        for num in str(number):
            if num == ".":
                break

            self.ufc(num)

        self.ufc("ENTER", delay_release=self.medium_delay)

        i = str(number).find(".")

        if two_enters:
            if i > 0:
                for num in str(number)[str(number).find(".") + 1:]:
                    self.ufc(num)

            self.ufc("ENTER", delay_release=self.medium_delay)

    def enter_coords(self, latlong, elev):
        lat_str, lon_str = latlon_tostring(latlong, decimal_minutes_mode=False, easting_zfill=3)
        self.logger.debug(f"{self.method} - Entering coords string: {lat_str}, {lon_str}")

        if latlong.lat.degree > 0:
            self.ufc("2", delay_release=self.medium_delay)
        else:
            self.ufc("8", delay_release=self.medium_delay)
        self.enter_number(lat_str)

        if latlong.lon.degree > 0:
            self.ufc("6", delay_release=self.medium_delay)
        else:
            self.ufc("4", delay_release=self.medium_delay)

        self.enter_number(lon_str)

        if elev:
            self.odu("3")
            self.enter_number(elev)

    def enter_waypoints(self, wps):
        self.lmpcd("2")

        for wp in wps:
            self.logger.info(f"Entering waypoint: {wp}")
            self.ufc("7")
            self.ufc("7")
            self.ufc("ENTER")
            self.odu("2")
            self.enter_coords(wp.position, wp.elevation)
            self.odu("1")

        self.lmpcd("2")

    def enter_all(self, profile):
        self.keylist = []
        self.enter_waypoints(self.validate_waypoints(profile.waypoints_as_list))
        if self.method != "DCS-BIOS":
            self.enter_keypress(self.keylist)


class MirageDriver(Driver):
    def __init__(self, logger, config):
        super().__init__(logger, config)
        self.limits = dict(WP=9)

    def pcn(self, num, delay_after=None, delay_release=None):
        if num in ("ENTER", "CLR"):
            key = f"INS_{num}_BTN"
        elif num == "PREP":
            key = "INS_PREP_SW"
        else:
            key = f"INS_BTN_{num}"

        self.press_with_delay(key, delay_after=delay_after, delay_release=delay_release)

    def ins_param(self, num, delay_after=None, delay_release=None):
        key = f"INS_PARAM_SEL {num}"
        self.press_with_delay(key, delay_after=delay_after,
                              delay_release=delay_release, raw=True)

    def enter_number(self, number):
        for num in str(number):
            if num == ".":
                continue

            self.pcn(num)
        self.pcn("ENTER")

    def enter_coords(self, latlong, elev=None):
        lat_str, lon_str = latlon_tostring(latlong, decimal_minutes_mode=True, easting_zfill=3, precision=3)
        self.logger.debug(f"{self.method} - Entering coords string: {lat_str}, {lon_str}")

        self.pcn("1")
        if latlong.lat.degree > 0:
            self.pcn("2", delay_release=self.medium_delay)
        else:
            self.pcn("8", delay_release=self.medium_delay)
        self.enter_number(lat_str)

        self.pcn("3")
        if latlong.lon.degree > 0:
            self.pcn("6", delay_release=self.medium_delay)
        else:
            self.pcn("4", delay_release=self.medium_delay)
        self.enter_number(lon_str)

        if elev or elev == 0:
            self.ins_param("3")
            self.pcn("1")
            if elev < 0:
                self.pcn("7")
            else:
                self.pcn("1")
            self.enter_number(elev)

    def enter_waypoints(self, wps):
        for i, wp in enumerate(wps, 1):
            self.logger.info(f"Entering waypoint: {wp}")
            self.ins_param("4")
            self.pcn("PREP")
            self.pcn("0")
            self.pcn(str(i))
            self.enter_coords(wp.position, wp.elevation)
        self.ins_param("4")

    def enter_all(self, profile):
        self.keylist = []
        self.enter_waypoints(self.validate_waypoints(profile.waypoints_as_list))
        if self.method != "DCS-BIOS":
            self.enter_keypress(self.keylist)


class TomcatDriver(Driver):
    def __init__(self, logger, config):
        super().__init__(logger, config)
        self.limits = dict(WP=3, FP=1, IP=1, ST=1, HA=1, DP=1, HB=1)

    def cap(self, num, delay_after=None, delay_release=None):
        raw = False
        cap_key_names = {
            "0": "RIO_CAP_BRG_",
            "1": "RIO_CAP_LAT_",
            "2": "RIO_CAP_NBR_",
            "3": "RIO_CAP_SPD_",
            "4": "RIO_CAP_ALT_",
            "5": "RIO_CAP_RNG_",
            "6": "RIO_CAP_LONG_",
            "8": "RIO_CAP_HDG_",
        }

        if num == "TAC":
            key = "RIO_CAP_CATRGORY 3"
            raw = True
        else:
            key = f"{cap_key_names.get(num, 'RIO_CAP_')}{num}"
        self.press_with_delay(key, delay_after=delay_after, delay_release=delay_release, raw=raw)

    def enter_number(self, number):
        for num in str(number):
            self.cap(num)
        self.cap("ENTER")

    def enter_coords(self, latlong, elev):
        lat_str, lon_str = latlon_tostring(latlong, one_digit_seconds=True)
        self.logger.debug(f"{self.method} - Entering coords string: {lat_str}, {lon_str}")

        self.cap("CLEAR")
        self.cap("1")
        if latlong.lat.degree > 0:
            self.cap("NE", delay_release=self.medium_delay)
        else:
            self.cap("SW", delay_release=self.medium_delay)
        self.enter_number(lat_str)

        self.cap("6")

        if latlong.lon.degree > 0:
            self.cap("NE", delay_release=self.medium_delay)
        else:
            self.cap("SW", delay_release=self.medium_delay)
        self.enter_number(lon_str)

        if elev:
            self.cap("4")
            self.enter_number(elev)

    def enter_waypoints(self, wps):
        cap_wp_type_buttons = dict(
            FP=4,
            IP=5,
            HB=6,
            DP=7,
            HA=8,
            ST=9
        )
        self.cap("TAC")
        for wp in wps:
            self.logger.info(f"Entering waypoint: {wp}")
            if wp.wp_type == "WP":
                self.cap(f"BTN_{wp.number}")
            else:
                self.cap(f"BTN_{cap_wp_type_buttons[wp.wp_type]}")

            self.enter_coords(wp.position, wp.elevation)
        self.cap("CLEAR")

    def enter_all(self, profile):
        self.keylist = []
        self.enter_waypoints(self.validate_waypoints(profile.waypoints_as_list))
        if self.method != "DCS-BIOS":
            self.enter_keypress(self.keylist)


class WarthogDriver(Driver):
    def __init__(self, logger, config):
        super().__init__(logger, config)
        self.limits = dict(WP=99)

    def aap(self, num, delay_after=None, delay_release=None):
        key = f"AAP_PAGE {num}"
        self.press_with_delay(key, delay_after=delay_after, delay_release=delay_release, raw=True)

    def cdu(self, num, delay_after=None, delay_release=None):
        key = f"CDU_{num}"
        self.press_with_delay(key, delay_after=delay_after, delay_release=delay_release)

    def clear_input(self, repeat=3):
        for i in range(0, repeat):
            self.cdu("CLR")

    def enter_waypoint_name(self, wp):
        result = re.sub(r'[^A-Za-z0-9 ]', '', wp.name)
        if result == "":
            result = f"WP{wp.number}"
        self.logger.debug("Waypoint name: " + result)
        self.clear_input()
        for character in result[0:12].upper():
            character = character.replace(" ", "SPC")
            self.cdu(character, delay_after=self.short_delay)

        self.cdu("LSK_3R")

    def enter_number(self, number):
        for num in str(number):
            if num != '.':
                self.cdu(num)

    def enter_coords(self, latlong):
        lat_str, lon_str = latlon_tostring(latlong, decimal_minutes_mode=True, easting_zfill=3, precision=3)
        self.logger.debug(f"{self.method} - Entering coords string: {lat_str}, {lon_str}")

        self.clear_input(repeat=2)

        if latlong.lat.degree > 0:
            self.cdu("N")
        else:
            self.cdu("S")
        self.enter_number(lat_str)
        self.cdu("LSK_7L")
        self.clear_input(repeat=2)

        if latlong.lon.degree > 0:
            self.cdu("E")
        else:
            self.cdu("W")
        self.enter_number(lon_str)
        self.cdu("LSK_9L")
        self.clear_input(repeat=2)

    def enter_elevation(self, elev):
        self.clear_input(repeat=2)
        self.enter_number(elev)
        self.cdu("LSK_5L")
        self.clear_input(repeat=2)

    def enter_waypoints(self, wps):
        self.aap("0")
        self.cdu("WP", self.short_delay)
        self.cdu("LSK_3L", self.medium_delay)
        self.logger.debug("Number of waypoints: " + str(len(wps)))
        for wp in wps:
            self.logger.info(f"Entering waypoint: {wp}")
            self.cdu("LSK_7R", self.short_delay)
            self.enter_waypoint_name(wp)
            self.enter_coords(wp.position)
            self.enter_elevation(wp.elevation)

    def enter_all(self, profile):
        self.keylist = []
        self.enter_waypoints(self.validate_waypoints(profile.waypoints_as_list))
        if self.method != "DCS-BIOS":
            self.enter_keypress(self.keylist)


class ViperDriver(Driver):
    def __init__(self, logger, config):
        super().__init__(logger, config)
        self.limits = dict(WP=127)

    def icp_btn(self, num, delay_after=None, delay_release=None):
        key = f"ICP_BTN_{num}"
        if num == "ENTR":
            key = "ICP_ENTR_BTN"
        self.press_with_delay(key, delay_after=delay_after, delay_release=delay_release)

    def icp_ded(self, num, delay_after=None, delay_release=None):
        if num == "DN":
            self.press_with_delay("ICP_DED_SW 0", delay_after=delay_after,
                                  delay_release=delay_release, raw=True)
        elif num == "UP":
            self.press_with_delay("ICP_DED_SW 2", delay_after=delay_after,
                                  delay_release=delay_release, raw=True)

        self.press_with_delay("ICP_DED_SW 1", delay_after=delay_after,
                              delay_release=delay_release, raw=True)

    def icp_data(self, num, delay_after=None, delay_release=None):
        if num == "DN":
            self.press_with_delay("ICP_DATA_UP_DN_SW 0", delay_after=delay_after,
                                  delay_release=delay_release, raw=True)
        elif num == "UP":
            self.press_with_delay("ICP_DATA_UP_DN_SW 2", delay_after=delay_after,
                                  delay_release=delay_release, raw=True)
        elif num == "RTN":
            self.press_with_delay("ICP_DATA_RTN_SEQ_SW 0", delay_after=delay_after,
                                  delay_release=delay_release, raw=True)

        self.press_with_delay("ICP_DATA_UP_DN_SW 1", delay_after=delay_after,
                              delay_release=delay_release, raw=True)
        self.press_with_delay("ICP_DATA_RTN_SEQ_SW 1", delay_after=delay_after,
                              delay_release=delay_release, raw=True)

    def enter_number(self, number):
        for num in str(number):
            if num != '.':
                self.icp_btn(num)

    def enter_elevation(self, elev):
        if elev < 0:
            self.icp_btn("0")
        self.enter_number(elev)
        self.icp_btn("ENTR")

    def enter_coords(self, latlong):
        lat_str, lon_str = latlon_tostring(latlong, decimal_minutes_mode=True, easting_zfill=3, precision=3, dfill=True)
        self.logger.debug(f"{self.method} - Entering coords string: {lat_str}, {lon_str}")

        if latlong.lat.degree > 0:
            self.icp_btn("2")
        else:
            self.icp_btn("8")
        self.enter_number(lat_str)
        self.icp_btn("ENTR")
        self.icp_data("DN")

        if latlong.lon.degree > 0:
            self.icp_btn("6")
        else:
            self.icp_btn("4")

        self.enter_number(lon_str)
        self.icp_btn("ENTR")
        self.icp_data("DN")

    def enter_waypoints(self, wps):
        self.icp_data("RTN")
        self.icp_btn("4", delay_release=1)

        for wp in wps:
            self.logger.info(f"Entering waypoint: {wp}")

            self.icp_data("DN")                     # To MAN/AUTO
            self.icp_data("DN")                     # To LAT

            self.enter_coords(wp.position)
            if wp.elevation or wp.elevation == 0:
                self.enter_elevation(wp.elevation)

            self.icp_data("UP")                     # To LON
            self.icp_data("UP")                     # To LAT
            self.icp_data("UP")                     # To MAN/AUTO
            self.icp_data("UP")                     # To STPT number
            self.icp_ded("UP")                      # Increment STPT number

        self.icp_ded("DN")                          # Backup to last STPT
        self.icp_data("RTN")

    def enter_all(self, profile):
        self.keylist = []
        self.enter_waypoints(self.validate_waypoints(profile.all_waypoints_as_list))
        if self.method != "DCS-BIOS":
            self.enter_keypress(self.keylist)


class ApachePilotDriver(Driver):
    def __init__(self, logger, config):
        super().__init__(logger, config)
        self.limits = dict(WP=None, HZ=None, CM=None, TG=None)

    def kbu(self, num, delay_after=None, delay_release=None):
        key = f"PLT_KU_{num}"
        self.press_with_delay(key, delay_after=delay_after,
                              delay_release=delay_release)

    def lmpd(self, pb, delay_after=None, delay_release=None):
        key = f"PLT_MPD_L_{pb}"
        self.press_with_delay(key, delay_after=delay_after,
                              delay_release=delay_release)

    def rmpd(self, pb, delay_after=None, delay_release=None):
        key = f"PLT_MPD_R_{pb}"
        self.press_with_delay(key, delay_after=delay_after,
                              delay_release=delay_release)

    def enter_number(self, number):
        for num in str(number):
            if num != ".":
                self.kbu(num)

    def enter_coords(self, latlong, elev=None):
        lat_str, lon_str = latlon_tostring(latlong, decimal_minutes_mode=True, easting_zfill=3, precision=2, dfill=True)
        self.logger.debug(f"{self.method} - Entering coords string: {lat_str}, {lon_str}")

        if latlong.lat.degree > 0:
            self.kbu("N", delay_release=self.medium_delay)
        else:
            self.kbu("S", delay_release=self.medium_delay)
        self.enter_number(lat_str)
        sleep(0.5)

        if latlong.lon.degree > 0:
            self.kbu("E", delay_release=self.medium_delay)
        else:
            self.kbu("W", delay_release=self.medium_delay)
        self.enter_number(lon_str)

        self.kbu("ENT")

        if elev:
            self.kbu("CLR")
            self.enter_number(elev)

        self.kbu("ENT")

    def enter_waypoints(self, wps):
        wp_type_buttons = dict(WP='L3', HZ='L4', CM='L5', TG='L6')
        if not wps:
            return

        self.rmpd("TSD")
        self.rmpd("B6") # POINT

        for wp in wps:
            self.logger.info(f"Entering waypoint: {wp}")
            self.rmpd("L2") # ADD
            self.rmpd(wp_type_buttons[wp.wp_type]) # WP TYPE
            self.rmpd("L1") # IDENT
            self.kbu("ENT") 
            if wp.name:
                free = wp.name.replace(' ', '')
                for char in free[0:3].upper():
                    self.kbu(char)
            self.kbu("ENT")
            self.kbu("CLR")

            self.enter_coords(wp.position, wp.elevation)

    def enter_all(self, profile):
        self.keylist = []
        self.enter_waypoints(self.validate_waypoints(profile.waypoints_as_list))
        if self.method != "DCS-BIOS":
            self.enter_keypress(self.keylist)


class ApacheGunnerDriver(Driver):
    def __init__(self, logger, config):
        super().__init__(logger, config)
        self.limits = dict(WP=None, HZ=None, CM=None, TG=None)

    def kbu(self, num, delay_after=None, delay_release=None):
        key = f"CPG_KU_{num}"
        self.press_with_delay(key, delay_after=delay_after,
                              delay_release=delay_release)

    def lmpd(self, pb, delay_after=None, delay_release=None):
        key = f"CPG_MPD_L_{pb}"
        self.press_with_delay(key, delay_after=delay_after,
                              delay_release=delay_release)

    def rmpd(self, pb, delay_after=None, delay_release=None):
        key = f"CPG_MPD_R_{pb}"
        self.press_with_delay(key, delay_after=delay_after,
                              delay_release=delay_release)

    def enter_number(self, number):
        for num in str(number):
            if num != ".":
                self.kbu(num)

    def enter_coords(self, latlong, elev=None):
        lat_str, lon_str = latlon_tostring(latlong, decimal_minutes_mode=True, easting_zfill=3, precision=2, dfill=True)
        self.logger.debug(f"{self.method} - Entering coords string: {lat_str}, {lon_str}")

        if latlong.lat.degree > 0:
            self.kbu("N", delay_release=self.medium_delay)
        else:
            self.kbu("S", delay_release=self.medium_delay)
        self.enter_number(lat_str)
        sleep(0.5)

        if latlong.lon.degree > 0:
            self.kbu("E", delay_release=self.medium_delay)
        else:
            self.kbu("W", delay_release=self.medium_delay)
        self.enter_number(lon_str)

        self.kbu("ENT")

        if elev:
            self.kbu("CLR")
            self.enter_number(elev)

        self.kbu("ENT")

    def enter_waypoints(self, wps):
        wp_type_buttons = dict(WP='L3', HZ='L4', CM='L5', TG='L6')
        if not wps:
            return

        self.rmpd("TSD")
        self.rmpd("B6") # POINT

        for wp in wps:
            self.logger.info(f"Entering waypoint: {wp}")
            self.rmpd("L2") # ADD
            self.rmpd(wp_type_buttons[wp.wp_type]) # WP TYPE
            self.rmpd("L1") # IDENT
            self.kbu("ENT") 
            if wp.name:
                free = wp.name.replace(' ', '')
                for char in free[0:3].upper():
                    self.kbu(char)
            self.kbu("ENT")
            self.kbu("CLR")

            self.enter_coords(wp.position, wp.elevation)

    def enter_all(self, profile):
        self.keylist = []
        self.enter_waypoints(self.validate_waypoints(profile.waypoints_as_list))
        if self.method != "DCS-BIOS":
            self.enter_keypress(self.keylist)


class BlackSharkDriver(Driver):
    def __init__(self, logger, config):
        super().__init__(logger, config)
        self.limits = dict(WP=6, TG=9)

    def pvi(self, num, delay_after=None, delay_release=None):
        key = f"PVI_{num}"
        self.press_with_delay(key, delay_after=delay_after,
                              delay_release=delay_release)

    def pvi_mode(self, num, delay_after=None, delay_release=None):
        key = f"PVI_MODES {num}"
        self.press_with_delay(key, delay_after=delay_after,
                              delay_release=delay_release, raw=True)

    def enter_number(self, number):
        for num in str(number):
            if num != ".":
                self.pvi(num)

    def enter_coords(self, latlong, elev=None):
        lat_str, lon_str = latlon_tostring(latlong, decimal_minutes_mode=True, easting_zfill=3, precision=1)
        self.logger.debug(f"{self.method} - Entering coords string: {lat_str}, {lon_str}")

        if latlong.lat.degree > 0:
            self.pvi("0")
        else:
            self.pvi("1")
        self.enter_number(lat_str)
        sleep(0.2)

        if latlong.lon.degree > 0:
            self.pvi("0")
        else:
            self.pvi("1")
        self.enter_number(lon_str)

        self.pvi("ENTER_BTN")

    def enter_waypoints(self, wps):
        wp_type_buttons = dict(WP='WAYPOINTS', TG='TARGETS')
        prev_type = None
        if not wps:
            return

        #Set NAV Master Mode ENT
        self.pvi_mode("2")
        for wp in wps:
            self.logger.info(f"Entering waypoint: {wp}")
            if wp.wp_type != prev_type:
                self.pvi(f"{wp_type_buttons[wp.wp_type]}_BTN")
                prev_type = wp.wp_type
            self.pvi(str(wp.number))
            self.enter_coords(wp.position)
        #Set NAV Master Mode OPER
        self.pvi_mode("3")

    def enter_all(self, profile):
        self.keylist = []
        self.enter_waypoints(self.validate_waypoints(profile.waypoints_as_list))
        if self.method != "DCS-BIOS":
            self.enter_keypress(self.keylist)

class StrikeEagleDriver(Driver):
    def __init__(self, logger, config):
        super().__init__(logger, config)
        self.limits = dict(WP=None, MSN=1)

    def ufc(self, num, delay_after=None, delay_release=None):
        ufc_key_names = {
            "1": "F_UFC_KEY_A",
            "2": "F_UFC_KEY_N",
            "3": "F_UFC_KEY_B",
            "4": "F_UFC_KEY_W",
            "5": "F_UFC_KEY_M",
            "6": "F_UFC_KEY_E",
            "7": "F_UFC_KEY__",
            "8": "F_UFC_KEY_S",
            "9": "F_UFC_KEY_C",
            "0": "F_UFC_KEY__",
        }

        key = f"{ufc_key_names.get(num, 'F_UFC_KEY_')}{num}"
        self.press_with_delay(key, delay_after=delay_after,
                              delay_release=delay_release)

    def ufc_pb(self, num, delay_after=None, delay_release=None):
        key = f"F_UFC_B{num}"
        self.press_with_delay(key, delay_after=delay_after,
                              delay_release=delay_release)

    def lmpd(self, num, delay_after=None, delay_release=None, repeat=1):
        key = f"F_MPD_L_B{num}"
        for _ in range(repeat):
            self.press_with_delay(key, delay_after=delay_after,
                                  delay_release=delay_release)

    def enter_number(self, number):
        for num in str(number):
            if num != ".":
                self.ufc(num)

    def enter_coords(self, latlong, elev, pp):
        lat_str, lon_str = latlon_tostring(latlong, decimal_minutes_mode=True, easting_zfill=3, precision=3)
        self.logger.debug(f"{self.method} - Entering coords string: {lat_str}, {lon_str}, {elev}")

        self.ufc("SHF")
        if latlong.lat.degree > 0:
            self.ufc("2")
        else:
            self.ufc("8")
        self.enter_number(lat_str)
        if not pp:
            self.ufc_pb("2")
        else:
            self.lmpd("8")
            self.lmpd("5")
        sleep(0.2)

        self.ufc("SHF")
        if latlong.lon.degree > 0:
            self.ufc("6")
        else:
            self.ufc("4")
        self.enter_number(lon_str)
        if not pp:
            self.ufc_pb("3")
        else:
            self.lmpd("8")
            self.lmpd("5")

        if elev:
            self.enter_number(elev)
            if not pp:
                self.ufc_pb("7")
            else:
                self.lmpd("8")

    def enter_waypoints(self, wps):
        if not wps:
            return

        seqmap = {
            "1": "A1",
            "2": "B3",
            "3": "C9"
        }

        wps = self.waypoints_by_sequence(wps)
        #Select Steerpoints
        self.ufc("CLR")
        self.ufc("CLR")
        self.ufc("DATA")
        #Select B
        self.ufc("SHF")
        self.ufc("3")
        self.ufc_pb("10")
        self.ufc_pb("10")
        for wp in wps:
            seq = seqmap[str(wp.sequence)] if wp.sequence > 0 else 'A1'
            self.logger.info(f"Entering waypoint: {wp}")
            self.ufc(str(wp.number))
            self.ufc("SHF")
            self.ufc(seq)
            self.ufc_pb("1")
            self.enter_coords(wp.position, wp.elevation, pp=False)
        #Select 1A
        self.ufc("DATA")
        self.ufc("1")
        self.ufc("SHF")
        self.ufc("1")
        self.ufc_pb("10")
        self.ufc("MENU")

    def enter_missions(self, missions):
        def stations_order(x):
            order = [2, 'L1', 'L2', 'L3', 5, 'R1', 'R2', 'R3', 8]
            return order.index(x)

        sorted_stations = list()
        stations = dict()
        for mission in missions:
            station_msn_list = stations.get(mission.station, list())
            station_msn_list.append(mission)
            stations[mission.station] = station_msn_list

        for k in sorted(stations, key=stations_order):
            sorted_stations.append(stations[k])

        self.ufc("CLR")
        self.ufc("CLR")
        self.ufc("CLR")
        self.ufc("MENU")
        self.lmpd("14")
        self.lmpd("9")
        self.lmpd("5", repeat=6)
        for msns in sorted_stations:
            if not msns:
                return

            for msn in msns:
                self.logger.info(f"Entering PP mission: {msn}")
                msn.elevation = max(1, msn.elevation)
                self.enter_coords(msn.position, msn.elevation, pp=True)
                self.lmpd("10", delay_after=self.medium_delay)
                sleep(1)
            self.lmpd("2")
            self.lmpd("4", repeat=2)
        self.lmpd("14", delay_after=self.medium_delay)

    def enter_all(self, profile):
        self.keylist = []
        self.enter_missions(self.validate_waypoints(profile.msns_as_list))
        sleep(1)
        self.enter_waypoints(self.validate_waypoints(profile.waypoints_as_list))
        if self.method != "DCS-BIOS":
            self.enter_keypress(self.keylist)
