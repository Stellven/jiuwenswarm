def parse_duration(s):
    text = s.strip()
    n = len(text)
    if not n:
        raise ValueError("empty duration")

    total = 0
    seen = 0
    i = 0

    while i < n:
        start = i
        while i < n and "0" <= text[i] <= "9":
            i += 1
        if i == start or i == n:
            raise ValueError("invalid duration term")

        unit = text[i]
        if unit == "s":
            bit, scale = 1, 1
        elif unit == "m":
            bit, scale = 2, 60
        elif unit == "h":
            bit, scale = 4, 3600
        elif unit == "d":
            bit, scale = 8, 86400
        else:
            raise ValueError("invalid duration term")

        if seen & bit:
            raise ValueError("repeated unit")
        seen |= bit
        total += int(text[start:i]) * scale
        i += 1

        while i < n and text[i] == " ":
            i += 1

    return total
