import json
import os


class Configuration(object):
    class ConfigError(Exception):
        pass

    def __init__(self, path, categories):
        # Reset properties
        self.bind = None
        self.server = None

        self.motd = {"modified": 0, "content": ""}
        self.rules = {"modified": 0, "content": ""}

        # Load configuration file and parse as JSON
        try:
            configuration = self.read_file(path + "pyrcd.json")
            configuration = json.loads(configuration[0])
        except json.decoder.JSONDecodeError as error:
            raise self.ConfigError("Configuration file has invalid contents (not parsable JSON): " + str(error))

        success, error = self.check_keys(configuration, categories)

        if not success:
            raise self.ConfigError(error)

        self.bind = configuration["bind"]
        self.server = configuration["server"]

        self.motd["content"], self.motd["modified"] = self.read_file(path + self.server["motd"])
        self.rules["content"], self.rules["modified"] = self.read_file(path + self.server["rules"])

    @staticmethod
    def read_file(file):
        with open(file) as handle:
            try:
                return handle.read(), os.path.getmtime(file)
            except (IOError, FileNotFoundError):
                raise Configuration.ConfigError("Could not read file '" + file + "'")

    @staticmethod
    def check_keys(configuration, categories):
        # Check top-level configuration keys
        if set(configuration.keys()) < set(categories.keys()):
            return False, "Some settings are missing"

        # Check second-level configuration keys
        for category in categories.keys():
            for setting in categories[category]:
                if setting not in configuration[category]:
                    return False, "'{0}' setting is missing from section [{1}]".format(str(setting), str(category))

        return True, ""
