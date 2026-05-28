"""
SPI Master Module for NOR Flash Memory Simulator.

Acts as the bridge between the Streamlit GUI (or any host controller)
and the SPI Slave. Constructs SPI command packets and sends them to
the slave for processing.
"""

import logging

from spi.spi_slave import (
    SPISlave,
    OPCODE_READ,
    OPCODE_WRITE,
    OPCODE_BLOCK_ERASE,
    OPCODE_READ_STATUS,
)

# Configure module logger
logger = logging.getLogger(__name__)


class SPIMaster:
    """
    SPI Master Controller.

    Bridges the GUI/host controller and the SPI slave by constructing
    SPI packets from high-level read/write/erase requests and sending
    them to the slave for execution.

    Attributes:
        spi_slave: Reference to the SPISlave instance.
    """

    def __init__(self, spi_slave: SPISlave):
        """
        Initialize the SPI master.

        Args:
            spi_slave: SPISlave instance to communicate with.
        """
        self.spi_slave = spi_slave
        logger.info("SPIMaster initialized")

    def read(self, address: int, length: int) -> bytes:
        """
        Perform a read operation via SPI.

        Builds a READ command packet and sends it to the SPI slave.
        For reads longer than 256 bytes, the request is split into
        multiple 256-byte transactions.

        Args:
            address: Starting linear byte address.
            length: Number of bytes to read.

        Returns:
            Read data as bytes.
        """
        logger.info("SPIMaster: READ request — address=0x%04X, length=%d", address, length)

        result = bytearray()
        remaining = length
        current_addr = address

        while remaining > 0:
            # SPI READ packet length field is 1 byte; 0 means 256
            chunk_len = min(remaining, 256)
            len_byte = chunk_len if chunk_len < 256 else 0

            # Build SPI READ packet: [0x03][A2][A1][A0][LEN]
            packet = bytes([
                OPCODE_READ,
                (current_addr >> 16) & 0xFF,
                (current_addr >> 8) & 0xFF,
                current_addr & 0xFF,
                len_byte,
            ])

            response = self.spi_slave.process_command(packet)
            result.extend(response)

            current_addr += chunk_len
            remaining -= chunk_len

        return bytes(result)

    def write(self, address: int, data: bytes | bytearray | list[int]) -> None:
        """
        Perform a write (page program) operation via SPI.

        Builds a WRITE command packet and sends it to the SPI slave.
        Data is sent in a single transaction (the slave handles
        page-boundary behavior via NOR constraints).

        Args:
            address: Starting linear byte address.
            data: Data bytes to program.
        """
        data = bytes(data)
        logger.info(
            "SPIMaster: WRITE request — address=0x%04X, length=%d",
            address, len(data),
        )

        # Build SPI WRITE packet: [0x02][A2][A1][A0][D0..Dn]
        packet = bytearray([
            OPCODE_WRITE,
            (address >> 16) & 0xFF,
            (address >> 8) & 0xFF,
            address & 0xFF,
        ])
        packet.extend(data)

        self.spi_slave.process_command(bytes(packet))

    def erase(self, block_id: int) -> None:
        """
        Perform a block erase operation via SPI.

        Args:
            block_id: Block index to erase (0 to blocks-1).
        """
        logger.info("SPIMaster: ERASE request — block=%d", block_id)

        # Build SPI BLOCK ERASE packet: [0xD8][BLOCK_ID]
        packet = bytes([OPCODE_BLOCK_ERASE, block_id])

        self.spi_slave.process_command(packet)

    def read_status(self) -> dict:
        """
        Read the device status register via SPI.

        Returns:
            Dictionary with parsed status fields:
                - busy: True if device is busy
                - raw: Raw status byte value
        """
        logger.info("SPIMaster: READ_STATUS request")

        # Build SPI READ STATUS packet: [0x05]
        packet = bytes([OPCODE_READ_STATUS])

        response = self.spi_slave.process_command(packet)
        status_byte = response[0] if response else 0x00

        return {
            "busy": bool(status_byte & 0x01),
            "raw": status_byte,
        }
