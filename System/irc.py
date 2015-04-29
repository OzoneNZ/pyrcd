class IRC(object):
    client_modes = {
        "i": 0,
        "w": 0,
        "x": 0
    }

    channel_modes = {
        "q": 1,
        "a": 1,
        "o": 1,
        "h": 1,
        "v": 1
    }

    channel_power_symbols = ["q", "a", "o", "h", "v"]

    channel_powers = {
        "q": "~",
        "a": "&",
        "o": "@",
        "h": "%",
        "v": "+"
    }

    @staticmethod
    def nick_valid(nick):
        characters = "abcdefghijklmonpqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890-_\\[]{}^`"

        if len(nick) == 0:
            return False

        for index in range(len(nick)):
            try:
                characters.index(nick[index])
            except ValueError:
                return False

        return True

    @staticmethod
    def mode_construct(modes):
        return "+" + ("".join(modes))

    @staticmethod
    def mode_deconstruct(valid_modes, mode_string, arguments):
        mode = None
        output = []
        count = 0

        for char in mode_string:
            if char not in ["+", "-"]:
                if mode is None:
                    break
            else:
                mode = char

            if char in valid_modes.keys():
                if valid_modes[char] > 0:
                    for parameter in range(valid_modes[char]):
                        if len(arguments) >= count + 1:
                            output.append({
                                "mode": mode,
                                "type": char,
                                "arguments": " ".join(arguments[count:count+valid_modes[char]])
                            })

                            count += 1
                else:
                    output.append({"type": char, "mode": mode, "arguments": None})

        return output