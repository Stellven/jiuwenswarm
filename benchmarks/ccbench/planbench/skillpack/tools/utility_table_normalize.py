"""utility.table_normalize

Parse an explicitly selected UTF-8 JSON/CSV file into ordered scalar rows without inference or value conversion
"""

TOOL_NAME = "utility.table_normalize"


def table_normalize(packet: dict) -> dict:
    """Parse an explicitly selected UTF-8 JSON/CSV file into ordered scalar rows without inference or value conversion.

    Args:
        packet: the packet to process (a dict).
    Returns:
        the resulting packet (a dict).
    """
    raise NotImplementedError("Not installed in the planning session; plan only.")
