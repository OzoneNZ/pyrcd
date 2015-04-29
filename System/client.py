import time
import socket
import threading

from System.irc import *


class Client(object):
    # Class constructor
    def __init__(self, server, handle, address):
        # Reset properties
        self.active = True

        # Client connection status
        self.connected = time.time()
        self.last_cmd = time.time()
        self.authorised = False
        self.pong = {"sent": 0, "pending": False}

        # Client attributes
        self.nick = None
        self.user = None
        self.name = None
        self.modes = []

        # Channel information
        self.channels = []
        self.channel_modes = {}

        # Initialise object
        self._server = server
        self._handle = handle

        # Client address information
        self.index = address[0] + ":" + str(address[1])
        self.ip_address = address[0]
        self.port = address[1]
        self.hostname = address[0]
        self.masked_hostname = self.calculate_hostname()

        # Enter a continuous loop
        self.loop()

    # String value substitution for quicker reply-building
    def substitute(self, buffer):
        substitutions = {
            # Server
            "fqdn": self._server.config.server["fqdn"],
            "server_name": self._server.config.server["name"],

            # Client
            "nick": self.nick if self.nick is not None else "*",
            "hostname": self.get_hostname(),
            "identifier": self.get_identifier()
        }

        for placeholder, value in substitutions.items():
            buffer = buffer.replace("{" + placeholder + "}", value)

        return buffer

    # Quicker socket "send" alias with the required unicode<->bytes conversion
    def write(self, buffer):
        try:
            if self._handle.send((buffer + "\r\n").encode("ascii")):
                self._server.log.custom("RAW", "[{0}:{1}] -> {2}".format(self.ip_address, self.port, buffer))
                return True
            else:
                return False
        except (OSError, BrokenPipeError):
            self.terminate()
        # return self._handle.send((buffer + "\r\n").encode("ascii"))

    # Main thread loop
    def loop(self):
        self._server.register_client(self)

        # Boot the client off the network if we're full
        if len(self._server.clients) >= self._server.config.server["client_limit"]:
            return self.close_link("Server is full; please try again later")

        # Hostname lookup
        try:
            lookup = threading.Thread(target=self.lookup_hostname, args=[])
            lookup.start()
        except threading.ThreadError:
            self.notice_auth("Failed to lookup hostname, using IP address (" + self.address + ") instead")

        # Loop indefinitely
        while True:
            # Break out if thread has been "killed"
            if not self.active:
                break

            try:
                data = []
                buffer = self._handle.recv(self._server.config.server["recv_buffer"])
                buffer = buffer.decode()

                for line in buffer.split("\n"):
                    if len(line):
                        data.append(line)
            except OSError:
                break

            for line in data:
                if self.active:
                    self.handle_data(line)
                else:
                    break

        # Kill the thread if main thread hasn't already done so
        if self.active:
            self.terminate()

    # Kill thread
    def terminate(self):
        self.active = False
        self._server.deregister_client(self)

        try:
            self._handle.shutdown(socket.SHUT_RDWR)
            self._handle.close()
        except OSError:
            pass

    # Reverse DNS lookup
    def lookup_hostname(self):
        self.notice_auth("Looking up your hostname...")

        try:
            hostname = socket.gethostbyaddr(self.ip_address)

            if len(hostname) == 3:
                self.hostname = hostname[0]
                self.notice_auth("Found your hostname (" + self.hostname + ")")
                self._server.log.custom("LOOKUP", "{0} resolves to {1}".format(self.ip_address, self.hostname))
            else:
                raise socket.herror()
        except socket.herror:
            self.notice_auth("Failed to lookup your hostname, using IP address instead (" + self.ip_address + ")")
            self._server.log.custom("LOOKUP", "{0} failed to resolve, continuing with IP address".format(self.ip_address))

    # Dynamic client hostname, depending on modes (not implemented yet)
    def get_hostname(self):
        if "x" in self.modes:
            return self.masked_hostname
        else:
            return self.hostname

    # Calculate a "masked" hostname for a client
    def calculate_hostname(self):
        full_address = self.ip_address.split(".")

        if len(full_address) == 4:
            return "{0}.{1}.x.x".format(full_address[0], full_address[1])
        else:
            return self.hostname

    # Get full identifier
    def get_identifier(self):
        if self.authorised:
            return "{0}!{1}@{2}".format(self.nick, self.user, self.get_hostname())
        else:
            return "{0}:{1}".format(self.ip_address, self.port)

    # Pulls out the command+arguments and passes them on
    def handle_data(self, arguments):
        arguments = arguments.strip("\r\n").split(" ")

        if len(arguments) < 1:
            return False

        command = arguments[0].upper()
        arguments = arguments[1:]

        if len(command):
            self.last_cmd = time.time()
            self._server.log.custom("RAW", "[{0}:{1}] <- {2}".format(self.ip_address, self.port, " ".join(arguments)))

            if not self.authorised:
                self.data_unregistered(command, arguments)
            else:
                self.data_registered(command, arguments)

    # Called when data is received by unregistered client
    def data_unregistered(self, command, arguments):
        commands = ["NICK", "USER", "PONG", "QUIT", "CAP"]

        if command in commands:
            self._server.log.custom("COMMAND", self.get_hostname() + ": " + command)

            method = getattr(self, "cmd_" + command.lower())
            method(arguments)
        else:
            self.num_451_not_registered(command)

    # Called when data is received by registered client
    def data_registered(self, command, arguments):
        commands = [
            "PRIVMSG", "NOTICE",            # Communication commands
            "NICK", "USER",                 # Client attribute stuff
            "PONG", "QUIT",                 # Connection stuff
            "WHOIS", "ISON", "USERHOST",    # User information
            "JOIN", "PART",                 # Channel stuff
            "MODE",                         # User/channel stuff
            "LUSERS", "MOTD", "RULES"       # Statistics and crap
        ]

        if command in commands:
            self._server.log.custom("COMMAND", self.get_identifier() + ": " + command)

            method = getattr(self, "cmd_" + command.lower())
            method(arguments)
        else:
            self.num_421_unknown_command(command)

    # Ping/pong function
    def ping(self):
        self.pong["sent"] = time.time()
        self.pong["pending"] = True
        self.write(self.substitute("PING :{fqdn}"))

    # Terminates client prematurely
    def close_link(self, buffer):
        if self.active:
            self.write(self.substitute("ERROR :Closing Link: {nick}[{hostname}] (" + buffer + ")"))
            self.terminate()

    # Called each time a NICK/USER call is made
    def check_authorisation(self):
        if not self.authorised:
            if self.nick is not None:
                if self.user is not None:
                    if self.name is not None:
                        if self.pong["pending"] is False and self.pong["sent"] > 0:
                            self.handle_authorised()

    # Client has authorised
    def handle_authorised(self):
        self.authorised = True

        buffer = [
            self.substitute(":{fqdn} 001 {nick} :Welcome to the {0} Network {1}").format(
                self._server.config.server["name"],
                self.get_identifier()
            ),

            self.substitute(":{fqdn} 002 {nick} :Your host is {fqdn}, running version pyrcd {0}").format(
                self._server.revision
            ),

            self.substitute(":{fqdn} 003 {nick} :This server was created {0}").format(
                time.strftime("%a %b %d %H:%M:%S %Y", time.localtime(self._server.started))
            )
        ]

        for line in buffer:
            self.write(line)

        # LUSERS statistics
        self.num_251_lusers_total()
        self.num_255_lusers_local_total()
        self.num_265_lusers_local_users()
        self.num_266_lusers_global_users()

        # Message of the Day
        self.num_375_motd_start()
        self.num_372_motd()
        self.num_376_motd_end()

        # Base modes
        self.mode_i("+", None)
        self.mode_w("+", None)
        self.mode_x("+", None)

        self._server.log.custom("AUTHORISED", self.get_identifier())

    # Handle client modes (either for self or external target)
    def handle_modes(self, modes, arguments):
        self._server.log.custom("MODE", "{0}: {1} {2}".format(
            self.get_identifier(),
            str(modes),
            str(arguments) if arguments is not None else ""
        ))

        if modes is not None:
            modes = IRC.mode_deconstruct(IRC.client_modes, modes, arguments)

            if len(modes):
                for bunch in modes:
                    method = getattr(self, "mode_" + bunch["mode"])

                    if method:
                        method(bunch["type"], bunch["arguments"])
        else:
            # User getting their own mode string
            self.num_221_user_modes()

    # BROADCAST: "MODE"
    def broadcast_modes(self, modes):
        return self.write(self.substitute(":{identifier} MODE {nick} " + modes))

    # NOTICE "AUTH"
    def notice_auth(self, buffer):
        self.write(self.substitute(":{fqdn} NOTICE AUTH :*** " + buffer))

    # NUMERIC: 221 "USER MODES"
    def num_221_user_modes(self):
        return self.write(self.substitute(":{fqdn} 221 {nick} " + IRC.mode_construct(self.modes)))

    # NUMERIC: 232 "RULES"
    def num_232_rules(self):
        for line in self._server.config.rules["content"].split("\n"):
            self.write(self.substitute(":{fqdn} 232 {nick} :- " + line))

    # NUMERIC: 251 "LUSERS TOTAL"
    def num_251_lusers_total(self):
        self.write(self.substitute(":{fqdn} 251 {nick} :There are {0} users on 1 server").format(
            len(self._server.clients)
        ))

    # NUMERIC: 255 "LUSERS LOCAL TOTAL"
    def num_255_lusers_local_total(self):
        self.write(self.substitute(":{fqdn} 255 {nick} :I have {0} users").format(
            len(self._server.clients)
        ))

    # NUMERIC: 265 "LUSERS LOCAL USERS"
    def num_265_lusers_local_users(self):
        self.write(self.substitute(":{fqdn} 265 {nick} :Current local users {0}, max {1}").format(
            len(self._server.clients),
            self._server.max_clients
        ))

    # NUMERIC: 266 "LUSERS GLOBAL USERS"
    def num_266_lusers_global_users(self):
        self.write(self.substitute(":{fqdn} 266 {nick} :Current global users {0}, max {1}").format(
            len(self._server.clients),
            self._server.max_clients
        ))

    # NUMERIC: 302 "USERHOST"
    def num_302_userhost(self, hosts):
        self.write(self.substitute(":{fqdn} 302 {nick} :" + (" ".join(hosts))))

    # NUMERIC: 303 "ISON"
    def num_303_ison(self, nicks):
        self.write(self.substitute(":{fqdn} 303 {nick} :" + (" ".join(nicks))))

    # NUMERIC: 308 "RULES START"
    def num_308_rules_start(self):
        self.write(self.substitute(":{fqdn} 308 {nick} :- {0} Server Rules").format(self._server.config.server["name"]))

    # NUMERIC: 309 "RULES END"
    def num_309_rules_stop(self):
        self.write(self.substitute(":{fqdn} 309 {nick} :End of /RULES command."))

    # NUMERIC: 311 "WHOIS"
    def num_311_whois(self, target):
        self.write(self.substitute(":{fqdn} 311 {nick} {0} {1} {2} * :{3}").format(
            target.nick,
            target.user,
            target.get_hostname(),
            target.name
        ))

    # NUMERIC: 312 "WHOIS"
    def num_312_whois(self, target):
        self.write(self.substitute(":{fqdn} 312 {nick} {0} {1} :{2}").format(
            target.nick,
            self._server.config.server["fqdn"],
            self._server.config.server["name"]
        ))

    # NUMERIC: 317 "WHOIS"
    def num_317_whois(self, target):
        self.write(self.substitute(":{fqdn} 317 {nick} {0} {1:.0f} {2} :seconds idle, signon time").format(
            target.nick,
            time.time() - target.last_cmd,
            target.connected
        ))

    # NUMERIC: 318 "END OF WHOIS LIST"
    def num_318_end_of_whois_list(self, target):
        self.write(self.substitute(":{fqdn} 318 {nick} " + target + " :End of /WHOIS list."))

    # NUMERIC: 319 "USER CHANNELS"
    def num_319_user_channels(self, target):
        # <- :irc.localhost 319 Blake Blake :@#test
        channels = []

        for channel in target.channels:
            if "q" in target.channel_modes[channel]:
                channels.append("~" + channel)
            elif "a" in target.channel_modes[channel]:
                channels.append("&" + channel)
            elif "o" in target.channel_modes[channel]:
                channels.append("@" + channel)
            elif "h" in target.channel_modes[channel]:
                channels.append("%" + channel)
            elif "v" in target.channel_modes[channel]:
                channels.append("+" + channel)
            else:
                channels.append(channel)

        self.write(self.substitute(":{fqdn} 319 {nick} " + target.nick + " :" + (" ".join(channels))))

    # NUMERIC: 324 "CHANNEL MODES"
    def num_324_channel_modes(self, target):
        channel = self._server.channels[target]

        if len(channel.modes):
            mode_keys = "".join(channel.modes.keys())
            mode_values = "".join(channel.modes.values())
        else:
            mode_keys = "+"
            mode_values = ""

        self.write(self.substitute(":{fqdn} 324 {nick} {0} {1} {2}").format(channel.name, mode_keys, mode_values))

    # NUMERIC: 329 "CHANNEL CREATION"
    def num_329_channel_creation(self, target):
        channel = self._server.channels[target]
        self.write(self.substitute(":{fqdn} 329 {nick} {0} {1:.0f}").format(
            channel.name,
            channel.created
        ))

    # NUMERIC: 332 "CHANNEL TOPIC"
    def num_332_channel_topic(self, target, topic):
        self.write(self.substitute(":{fqdn} 332 {nick} " + target + " :" + topic))

    # NUMERIC: 333 "CHANNEL TOPIC TIME"
    def num_333_channel_topic_time(self, target, edit_time, author):
        self.write(self.substitute(":{fqdn} 333 {nick} {0} {1} {2:.0f}").format(target, author, edit_time))

    # NUMERIC: 353 "NAMES"
    def num_353_names(self, channel, names):
        self.write(self.substitute(":{fqdn} 353 {nick} = {0} :{1}").format(channel, " ".join(names)))

    # NUMERIC: 366 "END OF NAMES"
    def num_366_end_of_names(self, target):
        self.write(self.substitute(":{fqdn} 366 {nick} " + target + " :End of /NAMES list."))

    # NUMERIC: 372 "MOTD"
    def num_372_motd(self):
        self.write(self.substitute(":{fqdn} 372 {nick} :- {0}").format(
            time.strftime("%d/%m/%Y %H:%M", time.localtime(self._server.config.motd["modified"]))
        ))

        for line in self._server.config.motd["content"].split("\n"):
            self.write(self.substitute(":{fqdn} 372 {nick} :- " + line))

    # NUMERIC: 375 "MOTD START"
    def num_375_motd_start(self):
        self.write(self.substitute(":{fqdn} 375 {nick} :- {server_name} Message of the Day -"))

    # NUMERIC: 376 "MOTD END"
    def num_376_motd_end(self):
        self.write(self.substitute(":{fqdn} 376 {nick} :End of /MOTD command."))

    # NUMERIC: 378 "WHOIS"
    def num_378_whois(self, target):
        self.write(self.substitute(":{fqdn} 378 {nick} {0} :is connecting from *@{1} {1}").format(
            target.nick,
            target.get_hostname()
        ))

    # NUMERIC: 401 "NO SUCH RECIPIENT"
    def num_401_no_such_recipient(self, target):
        self.write(self.substitute(":{fqdn} 401 {nick} " + target + " :No such nick/channel"))

    # NUMERIC: 403 "NO SUCH CHANNEL"
    def num_403_no_such_channel(self, target):
        self.write(self.substitute(":{fqdn} 403 {nick} " + target + " :No such channel"))

    # NUMERIC: 410 "INVALID CAP SUBCOMMAND"
    def num_410_invalid_cap_subcommand(self, subcommand):
        self.write(self.substitute(":{fqdn} 410 {nick} " + subcommand + " :Invalid CAP subcommand"))

    # NUMERIC: 411 "NO RECIPIENT"
    def num_411_no_recipient(self, command):
        self.write(self.substitute(":{fqdn} 411 {nick} :No recipient given (" + command + ")"))

    # NUMERIC: 412 "NO TEXT TO SEND"
    def num_412_no_text_to_send(self):
        self.write(self.substitute(":{fqdn} 412 {nick} :No text to send"))

    # NUMERIC: 421 "UNKNOWN COMMAND"
    def num_421_unknown_command(self, command):
        self.write(self.substitute(":{fqdn} 421 {nick} " + command + " :Unknown command"))

    # NUMERIC: 431 "NO NICK GIVEN"
    def num_431_no_nick_given(self, command):
        self.write(self.substitute(":{fqdn} 431 " + command + " :No nickname given"))

    # NUMERIC: 432 "NICK ALREADY TAKEN"
    def num_432_nick_already_taken(self, nick):
        self.write(self.substitute(":{fqdn} 432 {nick} " + nick + " :Nickname is already in use"))

    # NUMERIC: 442 "NOT ON CHANNEL"
    def num_442_not_on_channel(self, channel):
        self.write(self.substitute(":{fqdn} 442 " + channel + " :You're not on that channel"))

    # NUMERIC: 451 "NOT REGISTERED"
    def num_451_not_registered(self, command):
        self.write(self.substitute(":{fqdn} 451 " + command + " :You have not registered"))

    # NUMERIC: 461 "MORE PARAMETERS"
    def num_461_more_parameters(self, command):
        self.write(self.substitute(":{fqdn} 461 {nick} " + command + " :Not enough parameters"))

    # NUMERIC: 462 "ALREADY REGISTERED"
    def num_462_already_registered(self):
        self.write(self.substitute(":{fqdn} 462 {nick} USER :You may not reregister"))

    # COMMAND: "CAP"
    def cmd_cap(self, arguments):
        if len(arguments) == 0:
            self.num_461_more_parameters("CAP")
        elif arguments[0].upper() == "LS":
            self.write(self.substitute(":{fqdn} CAP {nick} LS :account-notify multi-prefix userhost-in-names"))
        else:
            self.num_410_invalid_cap_subcommand(arguments[0])

    # COMMAND: "ISON"
    def cmd_ison(self, arguments):
        if len(arguments) < 1:
            self.num_461_more_parameters("ISON")
        else:
            online = []

            for nick in arguments:
                if not self._server.nick_available(nick):
                    online.append(nick)

            self.num_303_ison(online)

    # COMMAND: "JOIN"
    def cmd_join(self, arguments):
        if len(arguments) < 1:
            self.num_461_more_parameters("JOIN")
        elif arguments[0][0] != "#":
            self.num_403_no_such_channel(arguments[0])
        else:
            if arguments[0] not in self.channels:
                if len(arguments) < 2:
                    arguments.append("")

                count = 1

                # Loop through all channels that have been provided
                for channel in arguments[0].split(","):
                    if count + 1 <= len(arguments):
                        key = arguments[count]
                    else:
                        key = None

                    self._server.channel_join(self.index, channel, key)
                    count += 1

    # COMMAND: "LUSERS"
    def cmd_lusers(self, arguments):
        self.num_251_lusers_total()
        self.num_255_lusers_local_total()
        self.num_265_lusers_local_users()
        self.num_266_lusers_global_users()

    # COMMAND: "MODE"
    def cmd_mode(self, arguments):
        if len(arguments) < 1:
            self.num_461_more_parameters("MODE")
        # Channel
        elif arguments[0][0] == "#":
            arguments[0] = arguments[0].lower()

            if arguments[0] in self.channels:
                # User is asking for modes of the channel
                if len(arguments) == 1:
                    self.num_324_channel_modes(arguments[0])
                    self.num_329_channel_creation(arguments[0])
                # User is trying to set modes
                else:
                    self._server.channels[arguments[0]].handle_mode(self, " ".join(arguments[1:]))
            else:
                self.num_403_no_such_channel(arguments[0])
        # User
        else:
            self.handle_modes(
                arguments[1] if len(arguments) >= 2 else None,
                " ".join(arguments[2:]) if len(arguments) >= 3 else None
            )

    # COMMAND: "MOTD"
    def cmd_motd(self, arguments):
        self.num_375_motd_start()
        self.num_372_motd()
        self.num_376_motd_end()

    # COMMAND: "NICK"
    def cmd_nick(self, arguments):
        if len(arguments) == 0:
                self.num_431_no_nick_given("NICK")
        else:
            arguments[0] = arguments[0][1:] if arguments[0][0] == ":" else arguments[0]
            arguments[0] = arguments[0:30] if len(arguments) > 30 else arguments[0]

            if IRC.nick_valid(arguments[0]):
                if self._server.nick_available(arguments[0]):
                    if self.nick is not None:
                        self._server.broadcast_nick(self.nick, arguments[0])
                        self._server.deregister_nick(self.nick)

                    self._server.register_nick(arguments[0], self.index)

                    if self.authorised:
                        self.write(self.substitute(":{identifier} NICK :" + arguments[0]))

                    self.nick = arguments[0]

                    if not self.authorised:
                        self.check_authorisation()
                else:
                    self.num_432_nick_already_taken(arguments[0])
            else:
                self.write(self.substitute(":{fqdn} 432 NICK :Erroneous Nickname: Illegal Characters"))

    # COMMAND: "NOTICE"
    def cmd_notice(self, arguments):
        if len(arguments) < 1:
            self.num_411_no_recipient("NOTICE")
        elif len(arguments) < 2:
            self.num_412_no_text_to_send()
        else:
            arguments[1] = arguments[1][1:] if arguments[1][0] == ":" else arguments[1]

            # Channel
            if arguments[0][0] == "#":
                self._server.channel_notice(self.index, arguments[0], " ".join(arguments[1:]))
            # User
            else:
                if not self._server.nick_available(arguments[0]):
                    self._server.private_notice(self.index, arguments[0], " ".join(arguments[1:]))
                else:
                    self.num_401_no_such_recipient(arguments[0])

    # COMMAND: "PART"
    def cmd_part(self, arguments):
        if len(arguments) < 1:
            self.num_461_more_parameters("PART")
        else:
            if len(arguments) < 2:
                arguments.append("Leaving")

            # Loop through all channels that have been provided
            for channel in arguments[0].split(","):
                if not self._server.channel_exists(channel):
                    self.num_403_no_such_channel(channel)
                elif channel not in self.channels:
                    self.num_442_not_on_channel(channel)
                else:
                    self._server.channel_part(self.index, channel, arguments[-1])

    # COMMAND: "PONG"
    def cmd_pong(self, arguments):
        if len(arguments) == 0:
            self.num_461_more_parameters("PONG")
        else:
            if self.pong["pending"]:
                if arguments[0] == (":" + self._server.config.server["fqdn"]):
                    self._server.log.custom("PONG", "{0}".format(self.get_identifier()))
                    self.pong["pending"] = False
                    self.check_authorisation()

    # COMMAND: "PRIVMSG"
    def cmd_privmsg(self, arguments):
        if len(arguments) < 1:
            self.num_411_no_recipient("PRIVMSG")
        elif len(arguments) < 2:
            self.num_412_no_text_to_send()
        else:
            arguments[1] = arguments[1][1:] if arguments[1][0] == ":" else arguments[1]

            # Channel
            if arguments[0][0] == "#":
                self._server.channel_message(self.index, arguments[0], " ".join(arguments[1:]))
            # User
            else:
                if not self._server.nick_available(arguments[0]):
                    self._server.private_message(self.index, arguments[0], " ".join(arguments[1:]))
                else:
                    self.num_401_no_such_recipient(arguments[0])

    # COMMAND: "QUIT"
    def cmd_quit(self, arguments):
        if len(arguments) == 0:
            if self.authorised:
                arguments.append(self.nick)
            else:
                arguments.append("*")
        else:
            arguments[0] = arguments[0][1:] if arguments[0][0] == ":" else arguments[0]

        arguments = " ".join(arguments)
        self._server.broadcast_quit(self.index, arguments)
        self.close_link("Quit: " + arguments)

    # COMMAND: "RULES"
    def cmd_rules(self, arguments):
        self.num_308_rules_start()
        self.num_232_rules()
        self.num_309_rules_stop()

    # COMMAND: "USER"
    def cmd_user(self, arguments):
        if len(arguments) < 4:
            self.num_461_more_parameters("USER")
        else:
            arguments[0] = arguments[0:30] if len(arguments) > 30 else arguments[0]
            arguments[3] = arguments[0:30] if len(arguments) > 30 else arguments[0]

            if not self.user:
                if arguments[0].isalnum():
                    self.user = arguments[0]
                    arguments[3] = arguments[3][1:] if arguments[3][0] == ":" else arguments[3]
                    self.name = " ".join(arguments[3:])
                    self.check_authorisation()
                else:
                    self.close_link("Hostile username. Please only use 0-9 a-z A-Z in your username")
            else:
                self.num_462_already_registered()

    # COMMAND: "USERHOST"
    def cmd_userhost(self, arguments):
        if len(arguments) < 1:
            self.num_461_more_parameters("USERHOST")
        else:
            online = []

            for nick in arguments:
                if not self._server.nick_available(nick):
                    online.append(
                        "{0}={1}".format(
                            nick,
                            self._server.clients[self._server.nicks[nick.lower()]].get_identifier()
                        )
                    )

            self.num_302_userhost(online)

    # COMMAND: "WHOIS"
    def cmd_whois(self, arguments):
        if len(arguments) < 1:
            self.num_431_no_nick_given("WHOIS")
        elif not self._server.nick_available(arguments[0]):
            target = self._server.clients[self._server.nicks[arguments[0].lower()]]
            self.num_311_whois(target)
            self.num_378_whois(target)

            # Not much point sending this when the target hasn't joined a channel
            if len(target.channels):
                self.num_319_user_channels(target)

            self.num_312_whois(target)
            self.num_317_whois(target)
            self.num_318_end_of_whois_list(arguments[0])
        else:
            self.num_401_no_such_recipient(arguments[0])
            self.num_318_end_of_whois_list(arguments[0])

    # MODE: "i"
    def mode_i(self, mode, arguments):
        if "i" not in self.modes and mode == "+":
            self.modes.append("i")
            return self.broadcast_modes("+i")
        elif "i" in self.modes and mode == "-":
            self.modes.remove("i")
            return self.broadcast_modes("-i")

    # MODE: "w"
    def mode_w(self, mode, arguments):
        if "w" not in self.modes and mode == "+":
            self.modes.append("w")
            return self.broadcast_modes("+w")
        elif "w" in self.modes and mode == "-":
            self.modes.remove("w")
            return self.broadcast_modes("-w")

    # MODE: "x"
    def mode_x(self, mode, arguments):
        if "x" not in self.modes and mode == "+":
            self.modes.append("x")
            return self.broadcast_modes("+x")
        elif "x" in self.modes and mode == "-":
            self.modes.remove("x")
            return self.broadcast_modes("-x")