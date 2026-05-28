"""
NOR Flash Storage Model for NOR Flash Memory Simulator.

Models the high-level functional behavior of a 64KB NOR Flash device,
including read, write (program), and erase operations with realistic
timing delays and NOR flash constraints (bits can only go 1→0 without erase).
"""

import time
import logging
import numpy as np

from utils.address import linear_to_hierarchy, hierarchy_to_linear
from utils.hexviewer import format_hex_dump
from utils import terminal as term

# Configure module logger
logger = logging.getLogger(__name__)


class NORStorage:
    """
    NOR Flash Memory Storage Model.

    Maintains a NumPy multidimensional array representing the NOR flash
    memory organized as blocks → sectors → pages → bytes. Supports
    read, write (program), and erase operations with configurable
    timing delays.

    Attributes:
        config: Configuration dictionary with flash geometry and timing.
        norarray: NumPy array storing the flash memory contents.
        status: Dictionary tracking current device status.
    """

    def __init__(self, config: dict):
        """
        Initialize the NOR flash storage.

        Args:
            config: Configuration dictionary containing:
                - blocks: Number of blocks
                - sectors_per_block: Sectors per block
                - pages_per_sector: Pages per sector
                - bytes_per_page: Bytes per page
                - read_delay_ms: Read latency in milliseconds
                - write_delay_ms: Write/program latency in milliseconds
                - erase_delay_ms: Erase latency in milliseconds
                - spi_mode: SPI bus mode string
        """
        self.config = config

        self.blocks = config["blocks"]
        self.sectors_per_block = config["sectors_per_block"]
        self.pages_per_sector = config["pages_per_sector"]
        self.bytes_per_page = config["bytes_per_page"]

        self.total_size = (
            self.blocks
            * self.sectors_per_block
            * self.pages_per_sector
            * self.bytes_per_page
        )

        # Timing delays (convert ms → seconds)
        self.read_delay = config.get("read_delay_ms", 10) / 1000.0
        self.write_delay = config.get("write_delay_ms", 100) / 1000.0
        self.erase_delay = config.get("erase_delay_ms", 500) / 1000.0

        # Initialize the NOR flash array — erased state is 0xFF
        self.norarray = np.full(
            (self.blocks, self.sectors_per_block, self.pages_per_sector, self.bytes_per_page),
            0xFF,
            dtype=np.uint8,
        )

        # Device status tracking
        self.status = {
            "busy": False,
            "last_op": "INIT",
            "spi_mode": config.get("spi_mode", "spi"),
        }

        # Subtask execution timing
        self.last_op_duration_ms = 0.0
        self.last_print_duration_ms = 0.0

        logger.info(
            "NORStorage initialized: %d blocks × %d sectors × %d pages × %d bytes = %d bytes (%d KB)",
            self.blocks,
            self.sectors_per_block,
            self.pages_per_sector,
            self.bytes_per_page,
            self.total_size,
            self.total_size // 1024,
        )

    def read(self, address: int, length: int) -> bytes:
        """
        Read bytes from the NOR flash starting at the given linear address.

        Handles cross-boundary reads seamlessly across pages, sectors, and blocks.

        Args:
            address: Starting linear byte address.
            length: Number of bytes to read.

        Returns:
            Read data as bytes.

        Raises:
            ValueError: If address or address+length is out of range.
        """
        if address < 0 or address >= self.total_size:
            raise ValueError(
                f"Read address 0x{address:04X} out of range (0x0000 - 0x{self.total_size - 1:04X})"
            )
        if address + length > self.total_size:
            raise ValueError(
                f"Read range 0x{address:04X} + {length} exceeds flash size (0x{self.total_size:04X})"
            )
        if length <= 0:
            raise ValueError("Read length must be positive")

        self.status["busy"] = True
        self.status["last_op"] = "READ"

        start_time = time.perf_counter()
        # Simulate read latency
        time.sleep(self.read_delay)

        data = bytearray()
        for i in range(length):
            block, sector, page, offset = linear_to_hierarchy(address + i, self.config)
            data.append(int(self.norarray[block, sector, page, offset]))

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        self.last_op_duration_ms = elapsed_ms
        self.status["busy"] = False

        logger.info(
            "READ: address=0x%04X, length=%d, data=%s",
            address,
            length,
            " ".join(f"{b:02X}" for b in data[:16]) + ("..." if length > 16 else ""),
        )

        # Terminal visualization
        t_print_start = time.perf_counter()
        term.print_read_header(address, length, elapsed_ms)
        term.print_hex_dump(format_hex_dump(bytes(data), address))
        status = self.get_status()
        term.print_status(status["busy"], status["last_op"], status["spi_mode"])
        self.last_print_duration_ms = (time.perf_counter() - t_print_start) * 1000.0

        return bytes(data)

    def write(self, address: int, data: bytes | bytearray | list[int]) -> None:
        """
        Write (program) bytes to the NOR flash starting at the given linear address.

        Enforces the NOR flash constraint: bits can only transition from 1→0.
        Writing is performed as new_value = old_value & incoming_data.
        A warning is logged if any byte attempts an illegal 0→1 transition.

        Args:
            address: Starting linear byte address.
            data: Data bytes to program.

        Raises:
            ValueError: If address or data range is out of bounds.
        """
        data = bytes(data)

        if address < 0 or address >= self.total_size:
            raise ValueError(
                f"Write address 0x{address:04X} out of range (0x0000 - 0x{self.total_size - 1:04X})"
            )
        if address + len(data) > self.total_size:
            raise ValueError(
                f"Write range 0x{address:04X} + {len(data)} exceeds flash size (0x{self.total_size:04X})"
            )
        if len(data) == 0:
            raise ValueError("Write data must not be empty")

        self.status["busy"] = True
        self.status["last_op"] = "WRITE"

        start_time = time.perf_counter()
        # Simulate write/program latency
        time.sleep(self.write_delay)

        illegal_transitions = 0
        for i, incoming_byte in enumerate(data):
            block, sector, page, offset = linear_to_hierarchy(address + i, self.config)
            old_value = int(self.norarray[block, sector, page, offset])

            # NOR flash constraint: bits can only go 1→0
            new_value = old_value & incoming_byte

            # Check for illegal 0→1 transitions
            if new_value != incoming_byte:
                illegal_transitions += 1

            self.norarray[block, sector, page, offset] = new_value

        if illegal_transitions > 0:
            logger.warning(
                "WRITE: %d byte(s) had illegal 0→1 transitions (NOR constraint applied: new = old & data)",
                illegal_transitions,
            )

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        self.last_op_duration_ms = elapsed_ms
        self.status["busy"] = False

        logger.info(
            "WRITE: address=0x%04X, length=%d, data=%s",
            address,
            len(data),
            " ".join(f"{b:02X}" for b in data[:16]) + ("..." if len(data) > 16 else ""),
        )

        # Terminal visualization — readback the written region
        t_print_start = time.perf_counter()
        term.print_write_header(address, len(data), elapsed_ms)
        if illegal_transitions > 0:
            term.print_write_warning(illegal_transitions)
        term.print_write_data(data)
        term.print_memory_label("Memory after write:")
        readback = bytearray()
        display_len = max(len(data), 16)
        for j in range(min(display_len, self.total_size - address)):
            b, s, p, o = linear_to_hierarchy(address + j, self.config)
            readback.append(int(self.norarray[b, s, p, o]))
        term.print_hex_dump(format_hex_dump(bytes(readback), address))
        status = self.get_status()
        term.print_status(status["busy"], status["last_op"], status["spi_mode"])
        self.last_print_duration_ms = (time.perf_counter() - t_print_start) * 1000.0

    def erase(self, block_id: int) -> None:
        """
        Erase an entire block, setting all bytes to 0xFF.

        Args:
            block_id: Block index to erase (0 to blocks-1).

        Raises:
            ValueError: If block_id is out of range.
        """
        if block_id < 0 or block_id >= self.blocks:
            raise ValueError(
                f"Block ID {block_id} out of range. Valid range: 0 - {self.blocks - 1}"
            )

        self.status["busy"] = True
        self.status["last_op"] = "ERASE"

        start_time = time.perf_counter()
        # Simulate erase latency
        time.sleep(self.erase_delay)

        # Set entire block to erased state (0xFF)
        self.norarray[block_id, :, :, :] = 0xFF

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        self.last_op_duration_ms = elapsed_ms
        self.status["busy"] = False

        logger.info("ERASE: block=%d — all bytes set to 0xFF", block_id)

        # Terminal visualization — show first 64 bytes of erased block
        t_print_start = time.perf_counter()
        block_start = block_id * self.sectors_per_block * self.pages_per_sector * self.bytes_per_page
        block_end = block_start + self.sectors_per_block * self.pages_per_sector * self.bytes_per_page - 1
        term.print_erase_header(block_id, block_start, block_end, elapsed_ms)
        readback = bytearray()
        for j in range(64):
            b, s, p, o = linear_to_hierarchy(block_start + j, self.config)
            readback.append(int(self.norarray[b, s, p, o]))
        term.print_hex_dump(format_hex_dump(bytes(readback), block_start))
        status = self.get_status()
        term.print_status(status["busy"], status["last_op"], status["spi_mode"])
        self.last_print_duration_ms = (time.perf_counter() - t_print_start) * 1000.0

    def get_status(self) -> dict:
        """
        Return the current device status.

        Returns:
            Dictionary with keys: busy, last_op, spi_mode.
        """
        return dict(self.status)

    def dump(self, start: int = 0, length: int = 256) -> str:
        """
        Return a hex dump of the specified memory region.

        Args:
            start: Starting linear address (default: 0).
            length: Number of bytes to dump (default: 256).

        Returns:
            Formatted hex dump string.
        """
        # Clamp to valid range
        start = max(0, min(start, self.total_size - 1))
        length = min(length, self.total_size - start)

        data = bytearray()
        for i in range(length):
            block, sector, page, offset = linear_to_hierarchy(start + i, self.config)
            data.append(int(self.norarray[block, sector, page, offset]))

        return format_hex_dump(bytes(data), start)
