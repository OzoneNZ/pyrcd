#!/usr/bin/env python3

# pyrcd libraries
from System.log import *
from System.configuration import *
from System.server import *


# Base directory of pyrcd
_HOME_ = os.path.dirname(os.path.realpath(__file__))

# Initialise some crap to suppress warnings
log = None
config = None
server = None

# Logging
try:
    log = Log(_HOME_ + "/Logs/", 1)
    log.info("pyrcd starting...")
except Log.LogError as error:
    sys.exit(str(error) + ", exiting.")

# Version check
if sys.version_info[0] != 3:
    log.error("pyrcd requires Python 3")

# Configuration
keys = {
    "bind": ["address", "port"],
    "server": ["debug", "fqdn", "name", "client_limit", "recv_buffer", "motd", "rules"]
}

try:
    config = Configuration(_HOME_ + "/Configuration/", keys)
    log.info("Configuration successfully loaded")
except Configuration.ConfigError as error:
    log.error(str(error) + ", exiting.")

log.debug = config.server["debug"]
log.info("Attempting to bind to {0}:{1}...".format(config.bind["address"], config.bind["port"]))

# Server socket
try:
    server = Server(config, log)
except Server.ServerError as error:
    log.error(str(error))

log.info("Successfully bound to {0}:{1}".format(config.bind["address"], config.bind["port"]))

# Enter continuous execution
try:
    server.tick()
except KeyboardInterrupt:
    log.info("Caught interrupt signal, exiting.")
    server.terminate_clients()
    server.terminate()