class IRC(object):
    client_modes = {
        "i": 0,
        "x": 0
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
                            output.append({"mode": mode, "type": char, "arguments": arguments})
                            count += 1
                else:
                    output.append({"type": mode, "mode": char, "arguments": None})

        return output