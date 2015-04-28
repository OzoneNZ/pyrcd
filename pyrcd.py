#!/usr/bin/env python3

# pyrcd libraries
from System.client import *
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

# Server PING check thread
server_loop = threading.Thread(target=server.loop)
server_loop.start()

# Continuous execution
while True:
    try:
        # Take in the client
        handle, address = server.accept()

        # Attempt to fork/thread the client
        try:
            client = threading.Thread(target=Client, args=[server, handle, address])
            client.start()
        except threading.ThreadError as error:
            log.warning("Failed to execute a client thread - this really shouldn't be happening...")
            log.warning(str(error))
            handle.close()

        # Return to idle for a bit - 100 CPU utilisation isn't so cool
        time.sleep(0.05)
    except KeyboardInterrupt:
        log.warning("Received interrupt signal, exiting.")
        server.terminate_all()

        break

# Run some cleanup code before terminating
server.terminate()