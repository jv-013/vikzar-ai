"""
Encoders used by the Lookup Engine.
"""


INTENSITY_ENCODING = {
    "Low": 1,
    "Medium": 2,
    "High": 3,
    "Very High": 4,
}


def encode_intensity(value: str) -> int:
    """
    Convert a textual intensity level into
    a numerical value.
    """
    return INTENSITY_ENCODING.get(value, 0)