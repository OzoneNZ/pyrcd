from System.irc import *

import time


class Channel(object):
    def __init__(self, server, channel):
        self._server = server

        self.name = channel
        self.created = time.time()
        self.destroyed = False

        self.clients = []
        self.modes = {}

        self.topic = {
            "content": "",
            "time": time.time(),
            "author": None
        }

    def broadcast_exclusive(self, exclusive_client, buffer):
        for client in self.clients:
            if client is not exclusive_client:
                client.write(buffer)

    def broadcast_inclusive(self, buffer):
        for client in self.clients:
            client.write(buffer)

    def join_client(self, client, key):
        self.clients.append(client)
        client.channels.append(self.name)
        join_string = client.substitute(":{identifier} JOIN " + self.name)

        # Only 1 client in the channel, give them operator
        if len(self.clients) == 1:
            client.channel_modes[self.name] = ["o"]
        else:
            client.channel_modes[self.name] = []

        # Start calculating a list of names/modes at the same time as broadcasting the JOIN
        names = []

        for channel_client in self.clients:
            channel_client.write(join_string)

            for power in IRC.channel_power_symbols:
                # Power found
                if power in channel_client.channel_modes[self.name]:
                    names.append(IRC.channel_powers[power] + channel_client.get_identifier())
                    break
                # Client has no power
                elif power == "v":
                    names.append(channel_client.get_identifier())

        if self.topic["author"] is not None:
            client.num_332_channel_topic(self.name, self.topic["content"])
            client.num_333_channel_topic_time(self.name, self.topic["time"], self.topic["author"])

        client.num_353_names(self.name, names)
        client.num_366_end_of_names(self.name)

    def remove_client(self, client, arguments):
        part_string = client.substitute(":{identifier} PART " + self.name + " :" + arguments)
        self.broadcast_inclusive(part_string)

        self.clients.remove(client)
        client.channels.remove(self.name)
        del client.channel_modes[self.name]

        # No clients left, destroy channel
        if len(self.clients) == 0:
            self.destroyed = True

    def handle_message(self, client, text):
        # Client is in channel
        if self.name in client.channels:
            message = client.substitute(":{identifier} PRIVMSG {0} :{1}").format(self.name, text)
            self.broadcast_exclusive(client, message)

            self._server.log.custom("PRIVMSG", "[{0} to {1}]: {2}".format(self.name, client.name, text))
        # Client in not in channel
        else:
            client.num_442_not_on_channel(self.name)

    def handle_notice(self, client, text):
        # Client is in channel
        if self.name in client.channels:
            message = client.substitute(":{identifier} NOTICE {0} :{1}").format(self.name, text)
            self.broadcast_exclusive(client, message)

            self._server.log.custom("NOTICE", "[{0} to {1}]: {2}".format(self.name, client.name, text))
        # Client in not in channel
        else:
            client.num_442_not_on_channel(self.name)

    def handle_mode(self, client, arguments):
        arguments = arguments.split(" ")
        modes = arguments[0]

        if len(arguments) >= 2:
            arguments = arguments[1:]
        else:
            arguments = []

        modes = IRC.mode_deconstruct(IRC.channel_modes, modes, arguments)

        for bunch in modes:
            try:
                method = getattr(self, "mode_" + bunch["type"])
                method(client, bunch["mode"], bunch["arguments"])
            except AttributeError:
                pass

    def mode_o(self, client, mode, arguments):
        nick_lower = arguments.lower()

        # Client is actually in this channel
        if self.name in client.channels:
            # User has op
            if "o" in client.channel_modes[self.name]:
                # User isn't trying to set op on themseves
                if nick_lower != client.nick.lower():
                    # Target is actually online
                    if nick_lower in self._server.nicks:
                        # Target is in this channel
                        if self._server.clients[self._server.nicks[nick_lower]] in self.clients:
                            target = self._server.clients[self._server.nicks[nick_lower]]
                            process = False

                            # User is trying to grant op
                            if mode == "+" and "o" not in target.channel_modes[self.name]:
                                target.channel_modes[self.name].append("o")
                                process = True
                            # User is trying to remove op
                            elif mode == "-" and "o" in target.channel_modes[self.name]:
                                target.channel_modes[self.name].remove("o")
                                process = True

                            if process:
                                self.broadcast_inclusive(":{0} MODE {1} {2}o {3}".format(
                                    client.get_identifier(),
                                    self.name,
                                    mode,
                                    target.nick
                                ))
                        # Target is not in this channel
                        else:
                            client.num_441_they_arent_on_channel(self.name, arguments)
                    # Target doesn't exist
                    else:
                        client.num_401_no_such_recipient(arguments)
            # User has halfop
            elif "h" in client.channel_modes[self.name]:
                client.num_460_halfops_cannot_set_mode("o")
            # User has no relevant power
            else:
                client.num_482_not_channel_operator(self.name)
        # Client isn't in this channel
        else:
            client.num_482_not_channel_operator()