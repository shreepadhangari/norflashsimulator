"""
Address Translation Utilities for NOR Flash Memory Simulator.

Provides conversion between linear (flat) byte addresses and the
hierarchical NOR flash structure (block, sector, page, byte offset).
"""


def linear_to_hierarchy(address: int, config: dict) -> tuple[int, int, int, int]:
    """
    Convert a linear byte address to hierarchical NOR flash coordinates.

    Args:
        address: Linear byte address (0 to flash_size - 1).
        config: Configuration dictionary with flash geometry parameters:
                - blocks: Number of blocks
                - sectors_per_block: Number of sectors per block
                - pages_per_sector: Number of pages per sector
                - bytes_per_page: Number of bytes per page

    Returns:
        Tuple of (block, sector, page, byte_offset).

    Raises:
        ValueError: If address is out of range.
    """
    blocks = config["blocks"]
    sectors_per_block = config["sectors_per_block"]
    pages_per_sector = config["pages_per_sector"]
    bytes_per_page = config["bytes_per_page"]

    total_size = blocks * sectors_per_block * pages_per_sector * bytes_per_page

    if address < 0 or address >= total_size:
        raise ValueError(
            f"Address 0x{address:04X} out of range. "
            f"Valid range: 0x0000 - 0x{total_size - 1:04X}"
        )

    # Calculate hierarchical coordinates from linear address
    byte_offset = address % bytes_per_page
    remaining = address // bytes_per_page

    page = remaining % pages_per_sector
    remaining = remaining // pages_per_sector

    sector = remaining % sectors_per_block
    block = remaining // sectors_per_block

    return (block, sector, page, byte_offset)


def hierarchy_to_linear(
    block: int, sector: int, page: int, offset: int, config: dict
) -> int:
    """
    Convert hierarchical NOR flash coordinates to a linear byte address.

    Args:
        block: Block index.
        sector: Sector index within the block.
        page: Page index within the sector.
        offset: Byte offset within the page.
        config: Configuration dictionary with flash geometry parameters.

    Returns:
        Linear byte address.

    Raises:
        ValueError: If any coordinate is out of range.
    """
    blocks = config["blocks"]
    sectors_per_block = config["sectors_per_block"]
    pages_per_sector = config["pages_per_sector"]
    bytes_per_page = config["bytes_per_page"]

    # Validate all coordinates
    if block < 0 or block >= blocks:
        raise ValueError(
            f"Block {block} out of range. Valid range: 0 - {blocks - 1}"
        )
    if sector < 0 or sector >= sectors_per_block:
        raise ValueError(
            f"Sector {sector} out of range. Valid range: 0 - {sectors_per_block - 1}"
        )
    if page < 0 or page >= pages_per_sector:
        raise ValueError(
            f"Page {page} out of range. Valid range: 0 - {pages_per_sector - 1}"
        )
    if offset < 0 or offset >= bytes_per_page:
        raise ValueError(
            f"Offset {offset} out of range. Valid range: 0 - {bytes_per_page - 1}"
        )

    linear = (
        block * (sectors_per_block * pages_per_sector * bytes_per_page)
        + sector * (pages_per_sector * bytes_per_page)
        + page * bytes_per_page
        + offset
    )
    return linear
