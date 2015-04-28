import os
import sys
import time

from Modules import colorama


colorama.init()


class Log(object):
    class LogError(Exception):
        pass

    # Logging "labels" - first indice is the debug level, second is the console colour
    labels = {
        # Top levels
        "INFO": (0, -1, "BLUE"),
        "WARNING": (0, -1, "YELLOW"),
        "ERROR": (0, -1, "RED"),

        # Basic logging
        "CONNECT": (1, -1, "GREEN"),
        "DISCONNECT": (1, -1, "RED"),
        "LOOKUP": (1, -1, "MAGENTA"),
        "AUTHORISED": (1, -1, "GREEN"),

        # Connection/channel logging
        "JOIN": (2, 4, "RED"),
        "PART": (2, 4, "RED"),

        # Stalker logging
        "PRIVMSG": (3, 4, "RED"),
        "MODE": (3, 4, "RED"),
        "NOTICE": (3, 4, "RED"),

        # Annoyingly verbose
        "COMMAND": (4, 4, "RED"),
        "PONG": (4, 4, "MAGENTA"),

        # Insanely verbose
        "RAW": (5, -1, "WHITE")
    }

    def __init__(self, directory, debug):
        # Reset properties
        self._handle = None
        self._directory = directory
        self._name = directory + time.strftime("%Y-%m-%d %H-%M-%S") + ".txt"
        self.debug = debug

        # Open log file
        self.open()

    def __del__(self):
        try:
            self._handle.close()
        except AttributeError:
            pass

    def open(self):
        if not os.access(self._directory, os.W_OK):
            raise Log.LogError("Directory '{0}' is not writable".format(self._directory))

        try:
            self._handle = open(self._name, "wb", 0)
        except IOError as error:
            raise Log.LogError("File '{0}' could not be opened for writing ({1})".format(self._name, error))

    def write(self, buffer):
        return self._handle.write(buffer.encode("utf-8"))

    def custom(self, label, text):
        output = False

        if label in self.labels:
            if self.labels[label][0] <= self.debug:
                if self.labels[label][1] == -1 or self.debug <= self.labels[label][1]:
                    output = True
        else:
            output = True

        if output:
            console_buffer = "[{0}] {1}[{2}]{3} {4}".format(
                time.strftime("%H:%M:%S"),
                getattr(colorama.Fore, self.labels[label][2]),
                label,
                colorama.Fore.RESET,
                text
            )

            # Specifically for log output; includes no colour chars
            file_buffer = "[{0}] [{1}] {2}\n".format(
                time.strftime("%H:%M:%S"),
                label,
                text
            )

            print(console_buffer)
            return self.write(file_buffer)

    def info(self, text):
        return self.custom("INFO", text)

    def warning(self, text):
        return self.custom("WARNING", text)

    def error(self, text):
        self.custom("ERROR", text)
        return sys.exit(1)