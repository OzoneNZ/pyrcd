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

            if "q" in channel_client.channel_modes[self.name]:
                names.append("~" + channel_client.get_identifier())
            elif "a" in channel_client.channel_modes[self.name]:
                names.append("&" + channel_client.get_identifier())
            elif "o" in channel_client.channel_modes[self.name]:
                names.append("@" + channel_client.get_identifier())
            elif "h" in channel_client.channel_modes[self.name]:
                names.append("%" + channel_client.get_identifier())
            elif "v" in channel_client.channel_modes[self.name]:
                names.append("+" + channel_client.get_identifier())
            else:
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