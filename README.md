# pyrcd

pyrcd is a (very) basic IRC daemon/server, implemented with Python 3.

# Features

pyrcd is by no means fully compatible with RFC 2813 and most likely never will be - I've based most functionality off how UnrealIRCd does things:

* Connect / disconnect (100% complete)
* Channels (20% complete)
	* JOIN
	* PART
	* Modes
		* Operator (+o) support
			* Not finished, ops can only grant/revoke op on other clients
* Client modes
	* +i (invisible)
	* +w (wallops broadcasts)
	* +x (masked hostnames)
* Private messaging (100% complete)
* Private noticing (100% complete)
* WHOIS lookup (100% complete)
* LUSERS (100% complete)

# Requirements

* Python **3** or above (**2.x is not supported** nor is future support planned)
* Read/write access over the directory it is run from


# Installation

Running `./pyrcd.py` should get it going in most environments - under Windows, you'll probably have to run something like `C:\Python34\python.exe "C:path\to\pyrcd.py"`

With the default configuration you should be able to start it out of the box with no issues - connecting to it with your IRC client is as simple as `/server 127.0.0.1:6667`


# Configuration

A basic configuration is supplied with pyrcd (includes all supported settings):

```json
{
   "bind": {
      "address": "127.0.0.1",
      "port": 6667
   },   
   "server": {
      "debug": "1",
      "fqdn": "fqdn",
      "name": "pyrcd daemon",
      "client_limit": 10,
      "recv_buffer": 512,
      "motd": "motd.txt",
      "rules": "rules.txt"
   },
}
```

You'll want to replace the following settings:

* `bind`
	* `address` - this is the IP address to which pyrcd binds
	* `port` - this is the port # to which pyrcd binds (6667 is used for most IRCd applications)
* `server`
	* `debug` - (currently) accepts values from 1-5 inclusive for varying degrees of log output:
		* `Server: 0` - INFO, WARNING, ERROR (all specific to pyrcd itself)
		* `Basic: 1` - *CONNECT, DISCONNECT, LOOKUP, AUTHORISED* - **default level**
		* `Connection + channel: 2` - *JOIN, PART*
		* `Stalker: 3` - *PRIVMSG, MODE, NOTICE*
		* `Annoying: 4` - *COMMAND, PONG*
		* `Insane: 5` - *RAW*
	* `fqdn` - **F**ully **Q**ualified **D**omain **N**ame of your IRC server
	* `name` - friendly name for IRC server, doesn't have to resolve to anything
	* `client_limit` - maximum # of clients that can be connected at once
	* `recv_buffer` - passed to `socket.recv()` as a maximum buffer length
	* `motd` - **M**essage **o**f **t**he  **D**ay file
	* `rules` - server rules file