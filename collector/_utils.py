import re


def parse_duration(duration: int | str) -> int:
    """Parses a duration value to seconds.

    The duration can be an integer or a string. If the duration is an integer, it will
    be returned as is, otherwise it will be parsed to seconds with a pattern described
    below.

    Regarding the string pattern, it must be a sequence of duration values separated by
    commas. Each duration value is formed by an optional number (which defaults to 1)
    and a time unit represented by a letter or a word (case-insensitive). The supported
    time units are as follows:

    - `months` (or `month`)
    - `weeks` (or `w`, `week`)
    - `days` (or `d`, `day`)
    - `hours` (or `h`, `hour`)
    - `minutes` (or `m`, `min`, `minute`)
    - `seconds` (or `s`, `sec`, `second`)

    It can optionally separate the number and the time unit by whitespace for each
    duration value.

    Args:
        duration (int | str): The duration to parse.

    Returns:
        int:
            The parsed duration in seconds. It will be rounded if the duration is a
            floating-point number.

    Raises:
        TypeError:
            If the duration is not an integer or a string.
        ValueError:
            If the duration is a string but the pattern is invalid.

    Example:
        >>> parse_duration(3600)
        3600
        >>> parse_duration("1 day")
        86400
        >>> parse_duration("1h")
        3600
        >>> parse_duration("1h, 30m")
        5400
        >>> parse_duration("3.14m")
        188
    """
    match duration:
        case int():
            return duration
        case str():
            return _parse_duration_pattern(duration)
        case _:
            raise TypeError("Invalid type of the duration. Expected int or str.")


def _parse_duration_pattern(duration: str) -> int:
    pattern = re.compile(
        r"(?:(?P<value>[\d\.]+)?\s*(?P<unit>[a-z]+)[\s\,]*)", flags=re.IGNORECASE
    )
    if not pattern.search(duration):
        raise ValueError("Invalid format of the duration string.")

    result = 0
    units = {
        r"months?": 2628000,
        r"w|weeks?": 604800,
        r"d|days?": 86400,
        r"h|hours?": 3600,
        r"m|min(?:ute)?s?": 60,
        r"s|sec(?:ond)?s?": 1,
    }

    for value, unit in pattern.findall(duration):
        try:
            base = float(value or 1)
        except ValueError as err:
            raise ValueError(
                f"The value '{value}' cannot be parsed as a number."
            ) from err

        try:
            multiplier = next(
                mul
                for reg, mul in units.items()
                if re.fullmatch(reg, unit, flags=re.IGNORECASE)
            )
        except StopIteration as err:
            raise ValueError(f"Unrecognized unit '{unit}'.") from err

        result += base * multiplier

    return round(result)
