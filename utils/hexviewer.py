"""
Hex Viewer Utility for NOR Flash Memory Simulator.

Formats raw byte data into a classic hex dump display with
address offsets, hexadecimal byte values, and ASCII representation.
"""


def format_hex_dump(
    data: bytes | bytearray,
    start_address: int = 0,
    bytes_per_line: int = 16,
) -> str:
    """
    Format raw byte data as a hex dump string.

    Output format per line:
        0x0000 : FF FF FF FF FF FF FF FF  FF FF FF FF FF FF FF FF  |................|

    Args:
        data: Raw byte data to format.
        start_address: Starting address to display in the address column.
        bytes_per_line: Number of bytes displayed per line (default: 16).

    Returns:
        Formatted hex dump string.
    """
    if not data:
        return "(empty)"

    lines = []
    for i in range(0, len(data), bytes_per_line):
        chunk = data[i : i + bytes_per_line]
        address = start_address + i

        # Address column
        addr_str = f"0x{address:04X}"

        # Hex bytes column — split into two groups for readability
        hex_parts = []
        for j, byte in enumerate(chunk):
            hex_parts.append(f"{byte:02X}")
        
        # Split hex into two halves
        half = bytes_per_line // 2
        left_hex = " ".join(hex_parts[:half])
        right_hex = " ".join(hex_parts[half:])

        # Pad if the last line is shorter than bytes_per_line
        left_pad = half * 3 - 1  # "XX " * half - trailing space
        right_pad = (bytes_per_line - half) * 3 - 1

        hex_str = f"{left_hex:<{left_pad}}  {right_hex:<{right_pad}}"

        # ASCII column
        ascii_chars = []
        for byte in chunk:
            if 0x20 <= byte <= 0x7E:
                ascii_chars.append(chr(byte))
            else:
                ascii_chars.append(".")
        ascii_str = "".join(ascii_chars)

        lines.append(f"{addr_str} : {hex_str}  |{ascii_str}|")

    return "\n".join(lines)


def format_compact_hex(data: bytes | bytearray, bytes_per_line: int = 8) -> str:
    """
    Format raw byte data as a compact hex string (no ASCII column).

    Output format per line:
        0x0000 : FF FF FF FF FF FF FF FF

    Args:
        data: Raw byte data to format.
        bytes_per_line: Number of bytes per line (default: 8).

    Returns:
        Formatted compact hex string.
    """
    if not data:
        return "(empty)"

    lines = []
    for i in range(0, len(data), bytes_per_line):
        chunk = data[i : i + bytes_per_line]
        hex_str = " ".join(f"{b:02X}" for b in chunk)
        lines.append(f"0x{i:04X} : {hex_str}")

    return "\n".join(lines)
