from time import sleep
from src.objects import base_files, default_bases
from src.db import DatabaseInterface
from src.logger import get_logger
from src.drivers import HornetDriver, HarrierDriver, MirageDriver, TomcatDriver, DriverException,\
                        WarthogDriver, ViperDriver, ApachePilotDriver, ApacheGunnerDriver, BlackSharkDriver
import json


class WaypointEditor:

    def __init__(self, settings):
        self.logger = get_logger("driver")
        self.settings = settings
        self.db = DatabaseInterface(settings['PREFERENCES'].get("DB_Name", "profiles.db"))
        self.default_bases = default_bases
        self.base_files = base_files
        self.drivers = dict(hornet=HornetDriver(self.logger, settings),
                            harrier=HarrierDriver(self.logger, settings),
                            mirage=MirageDriver(self.logger, settings),
                            tomcat=TomcatDriver(self.logger, settings),
                            warthog=WarthogDriver(self.logger, settings),
                            viper=ViperDriver(self.logger, settings),
                            apachep=ApachePilotDriver(self.logger, settings),
                            apacheg=ApacheGunnerDriver(self.logger, settings),
                            blackshark=BlackSharkDriver(self.logger, settings))
        self.driver = self.drivers["hornet"]
        self.driverCmd = dict()

    def set_driver(self, driver_name):
        try:
            self.driver = self.drivers[driver_name]
            with open(".\\cmd\\" + driver_name + ".json", "r") as f:
                try:
                    self.driverCmd = json.load(f)
                    self.logger.info(f"Commands loaded for {driver_name}: {driver_name}.json")
                except AttributeError:
                    self.logger.warning(f"Failed to read aircraft cmd: {driver_name}", exc_info=True)
        except KeyError:
            raise DriverException(f"Undefined driver: {driver_name}")
        except FileNotFoundError:
            self.logger.warning(f"No command file found for {driver_name} - use DCS-BIOS")

    def enter_all(self, profile, method):
        self.driver.method = method
        self.driver.cmdlist = self.driverCmd
        self.logger.info(f"Entering waypoints for aircraft: {profile.aircraft}")
        sleep(int(self.settings['PREFERENCES'].get('Grace_Period', 5)))
        self.driver.enter_all(profile)

    def stop(self):
        self.db.close()
        if self.driver is not None:
            self.driver.stop()
