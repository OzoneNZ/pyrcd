import socket

from System.channel import *


class Server(object):
    class ServerError(Exception):
        pass

    def __init__(self, config, log):
        # Reset properties
        self._handle = None
        self.revision = 0.1

        self.active = True
        self.started = time.time()

        self.config = None
        self.log = None

        self.max_clients = 0
        self.clients = {}
        self.nicks = {}
        self.nicks_cased = {}

        self.channels = {}
        self.channels_cased = {}

        # Initialise server socket
        try:
            self._handle = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._handle.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._handle.bind((config.bind["address"], config.bind["port"]))
            self._handle.listen(10)
        except socket.error as error:
            raise self.ServerError("Failed to bind socket: " + str(error))

        self.config = config
        self.log = log

    def accept(self):
        return self._handle.accept()

    def loop(self):
        while self.active:
            self.inactive_client_check()

            time.sleep(1)

    def inactive_client_check(self):
        try:
            for key, client in self.clients.items():
                # Check for clients that haven't responded to a ping in >=60 seconds
                if hasattr(client, "pong"):
                    if time.time() - client.pong["sent"] >= 60:
                        if client.pong["pending"]:
                            client.close_link("Ping timeout: {0:.0f} seconds".format(time.time() - client.pong["sent"]))
                        else:
                            client.ping()
                    elif client.pong["sent"] == 0 and not client.pong["pending"]:
                        client.ping()

                # Check for clients that haven't authorised in >=10 seconds
                if hasattr(client, "connected"):
                    if not client.authorised:
                        if time.time() - client.connected >= 10:
                            client.close_link("Ping timeout: {0:.0f} seconds".format(time.time() - client.connected))
        except RuntimeError:
            pass

    def register_client(self, client):
        self.log.custom("CONNECT", "{0}:{1}".format(client.ip_address, client.port))
        self.clients[client.index] = client

        if len(self.clients) > self.max_clients:
            self.max_clients = len(self.clients)

    def deregister_client(self, client):
        if client.nick is not None:
            self.deregister_nick(client.nick)

        self.log.custom("DISCONNECT", "{0}:{1}".format(client.ip_address, client.port))
        self.clients.pop(client.index, None)

    def nick_available(self, nick):
        return nick.lower() not in self.nicks

    def register_nick(self, nick, index):
        self.nicks[nick.lower()] = index
        self.nicks_cased[nick.lower()] = nick

    def deregister_nick(self, nick):
        self.nicks.pop(nick.lower(), None)
        self.nicks_cased.pop(nick.lower(), None)

    def broadcast_nick(self, old_nick, new_nick):
        client = self.clients[self.nicks[old_nick.lower()]]
        completed = [client]

        for channel in client.channels:
            channel = self.channels[channel.lower()]

            for server_client in channel.clients:
                if server_client not in completed:
                    server_client.write(client.substitute(":{identifier} NICK :" + new_nick))
                else:
                    completed.append(server_client)

    def broadcast_quit(self, index, reason):
        client = self.clients[index]
        completed = [client]

        for channel in client.channels:
            channel = self.channels[channel.lower()]

            for server_client in channel.clients:
                if server_client not in completed:
                    server_client.write(client.substitute(":{identifier} QUIT :" + reason))
                else:
                    completed.append(server_client)

    def terminate(self):
        self.active = False
        self._handle.close()

    def register_channel(self, channel, channel_object):
        self.channels[channel.lower()] = channel_object
        self.channels_cased[channel.lower()] = channel

    def deregister_channel(self, channel):
        self.channels.pop(channel.lower(), None)
        self.channels_cased.pop(channel.lower(), None)

    def channel_exists(self, channel):
        return channel.lower() in self.channels

    def terminate_all(self):
        for client in set(self.clients):
            self.clients[client].active = False
            self.clients[client].terminate()

    def private_message(self, client_index, target_nick, text):
        client = self.clients[client_index]
        target = self.clients[self.nicks[target_nick.lower()]]

        target.write(client.substitute(":{identifier} PRIVMSG {0} :{1}").format(target.nick, text))
        self.log.custom("PRIVMSG", "[{0}] [1]: {2}".format(client.nick, target.nick, text))

    def channel_message(self, client_index, target_channel, text):
        client = self.clients[client_index]

        # Channel exists
        if target_channel.lower() in self.channels:
            channel = self.channels[target_channel.lower()]
            channel.handle_message(client, text)
        # Channel does not exist
        else:
            client.num_403_no_such_channel(target_channel)

    def private_notice(self, client_index, target_nick, text):
        client = self.clients[client_index]
        target = self.clients[self.nicks[target_nick.lower()]]

        target.write(client.substitute(":{identifier} NOTICE {0} :{1}").format(target.nick, text))
        self.log.custom("NOTICE", "[{0} to {1}]: {2}".format(client.nick, target.nick, text))

    def channel_notice(self, client_index, target_channel, text):
        client = self.clients[client_index]

        # Channel exists
        if target_channel.lower() in self.channels:
            channel = self.channels[target_channel.lower()]
            channel.handle_notice(client, text)
        # Channel does not exist
        else:
            client.num_403_no_such_channel(target_channel)

    def channel_join(self, client_index, target_channel, arguments):
        client = self.clients[client_index]

        # Channel already exists
        if target_channel.lower() in self.channels:
            channel = self.channels[self.channels_cased[target_channel.lower()]]
            channel.join_client(client, arguments)
        # Channel doesn't exist
        else:
            channel = Channel(self, target_channel)
            self.register_channel(channel.name, channel)
            channel.join_client(client, arguments)

        self.log.custom("JOIN", "[{0}]: {1}".format(channel.name, client.nick))

    def channel_part(self, client_index, target_channel, arguments):
        client = self.clients[client_index]
        channel = self.channels[self.channels_cased[target_channel.lower()]]

        channel.remove_client(client, arguments)
        self.log.custom("PART", "[{0}]: {1}".format(channel.name, client.nick))

        if channel.destroyed:
            self.deregister_channel(channel.name)