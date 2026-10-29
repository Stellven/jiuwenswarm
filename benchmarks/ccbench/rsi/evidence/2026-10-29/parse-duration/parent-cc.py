def parse_duration(s):
    units = {"d": 86400, "h": 3600, "m": 60, "s": 1}
    text = s.strip()
    if not text:
        raise ValueError("empty duration")

    total = 0
    seen = set()
    i = 0

    while i < len(text):
        start = i
        while i < len(text) and text[i].isascii() and text[i].isdigit():
            i += 1
        if i == start or i == len(text) or text[i] not in units:
            raise ValueError("invalid duration term")

        unit = text[i]
        if unit in seen:
            raise ValueError("repeated unit")
        seen.add(unit)
        total += int(text[start:i]) * units[unit]
        i += 1

        if i < len(text) and text[i] == " ":
            while i < len(text) and text[i] == " ":
                i += 1
            if i == len(text):
                break
            if not (text[i].isascii() and text[i].isdigit()):
                raise ValueError("invalid duration term")

    return total
