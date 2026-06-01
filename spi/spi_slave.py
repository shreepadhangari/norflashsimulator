"""
SPI Slave Module for NOR Flash Memory Simulator.

Receives SPI command packets, decodes opcodes, interacts with the
NORStorage backend, and returns response data. Supports configurable
SPI bus width (SPI / QSPI / Octal SPI).
"""

import logging
import time
from datetime import datetime

from storage.norstorage import NORStorage
from utils.hexviewer import format_hex_dump
from utils import terminal as term

# Configure module logger
logger = logging.getLogger(__name__)

# SPI Opcode definitions
OPCODE_READ = 0x03
OPCODE_WRITE = 0x02
OPCODE_BLOCK_ERASE = 0xD8
OPCODE_READ_STATUS = 0x05

# Opcode name lookup
OPCODE_NAMES = {
    OPCODE_READ: "READ",
    OPCODE_WRITE: "WRITE/PAGE_PROGRAM",
    OPCODE_BLOCK_ERASE: "BLOCK_ERASE",
    OPCODE_READ_STATUS: "READ_STATUS",
}

# SPI mode transfer width multipliers
SPI_MODE_WIDTHS = {
    "spi": 1,
    "qspi": 4,
    "octal": 8,
}


class SPISlave:
    """
    SPI Slave Interface for NOR Flash.

    Receives and decodes SPI command packets, dispatches operations
    to the NORStorage backend, and returns response data. Maintains
    a transaction log for terminal visualization.

    Attributes:
        nor_storage: Reference to the NORStorage instance.
        spi_mode: Current SPI bus mode ("spi", "qspi", or "octal").
        bus_width: Number of bits transferred per clock cycle.
        last_command: Info dict about the most recently processed command.
        transaction_log: List of all processed transactions with timestamps.
    """

    def __init__(self, nor_storage: NORStorage, spi_mode: str = "spi"):
        """
        Initialize the SPI slave.

        Args:
            nor_storage: NORStorage instance to interact with.
            spi_mode: SPI bus mode — "spi" (1-bit), "qspi" (4-bit), or "octal" (8-bit).
        """
        self.nor_storage = nor_storage
        self.set_spi_mode(spi_mode)

        # Load SPI bus frequency configuration
        spi_clock_mhz = self.nor_storage.config.get("spi_clock_mhz", 10.0)
        self.spi_clock_hz = spi_clock_mhz * 1_000_000.0

        self.last_command: dict | None = None
        self.transaction_log: list[dict] = []

        logger.info(
            "SPISlave initialized in %s mode (bus width: %d-bit, speed: %.1f MHz)",
            self.spi_mode,
            self.bus_width,
            spi_clock_mhz,
        )

    def set_spi_mode(self, mode: str) -> None:
        """
        Set the SPI bus mode.

        Args:
            mode: "spi", "qspi", or "octal".

        Raises:
            ValueError: If mode is not recognized.
        """
        mode = mode.lower().strip()
        if mode not in SPI_MODE_WIDTHS:
            raise ValueError(
                f"Unknown SPI mode '{mode}'. Valid modes: {list(SPI_MODE_WIDTHS.keys())}"
            )
        self.spi_mode = mode
        self.bus_width = SPI_MODE_WIDTHS[mode]
        # Update the NOR storage status to reflect the new mode
        self.nor_storage.status["spi_mode"] = mode
        logger.info("SPI mode set to %s (%d-bit bus width)", mode.upper(), self.bus_width)

    def process_command(self, packet: bytes | bytearray | list[int]) -> bytes:
        """
        Process an incoming SPI command packet.

        Packet formats:
            READ:         [0x03][A2][A1][A0][LEN]        → returns LEN data bytes
            WRITE:        [0x02][A2][A1][A0][D0..Dn]     → programs data, returns status byte
            BLOCK_ERASE:  [0xD8][BLOCK_ID]               → erases block, returns status byte
            READ_STATUS:  [0x05]                          → returns status byte

        Args:
            packet: Raw SPI command packet as bytes.

        Returns:
            Response data as bytes.

        Raises:
            ValueError: If the packet is malformed or contains an unknown opcode.
        """
        packet = bytes(packet)

        if len(packet) < 1:
            raise ValueError("Empty SPI packet received")

        start_time = time.perf_counter()
        opcode = packet[0]
        op_name = self._decode_opcode(opcode)
        timestamp = datetime.now()

        logger.info("SPI RX: opcode=0x%02X (%s), packet_len=%d", opcode, op_name, len(packet))

        # Simulate SPI transfer overhead based on bus width
        transfer_bits = len(packet) * 8
        effective_clocks = transfer_bits / self.bus_width
        logger.debug(
            "SPI transfer: %d bits / %d-bit bus = %.0f effective clock cycles",
            transfer_bits, self.bus_width, effective_clocks,
        )

        response = b""
        address = None
        length = None
        block_id = None

        # Terminal: print SPI command header
        term.print_spi_header(opcode, op_name, self.spi_mode, self.bus_width, packet)

        try:
            if opcode == OPCODE_READ:
                # READ: [0x03][A2][A1][A0][LEN]
                if len(packet) < 5:
                    raise ValueError(
                        f"READ packet too short: expected 5 bytes, got {len(packet)}"
                    )
                address = (packet[1] << 16) | (packet[2] << 8) | packet[3]
                length = packet[4]
                if length == 0:
                    length = 256  # 0 means 256 bytes
                response = self.nor_storage.read(address, length)

            elif opcode == OPCODE_WRITE:
                # WRITE: [0x02][A2][A1][A0][D0..Dn]
                if len(packet) < 5:
                    raise ValueError(
                        f"WRITE packet too short: expected at least 5 bytes, got {len(packet)}"
                    )
                address = (packet[1] << 16) | (packet[2] << 8) | packet[3]
                data = packet[4:]
                length = len(data)
                self.nor_storage.write(address, data)
                response = bytes([0x00])  # Success status

            elif opcode == OPCODE_BLOCK_ERASE:
                # BLOCK ERASE: [0xD8][BLOCK_ID]
                if len(packet) < 2:
                    raise ValueError(
                        f"BLOCK_ERASE packet too short: expected 2 bytes, got {len(packet)}"
                    )
                block_id = packet[1]
                self.nor_storage.erase(block_id)
                response = bytes([0x00])  # Success status

            elif opcode == OPCODE_READ_STATUS:
                # READ STATUS: [0x05]
                status = self.nor_storage.get_status()
                status_byte = 0x00
                if status["busy"]:
                    status_byte |= 0x01  # Bit 0: BUSY flag
                response = bytes([status_byte])

            else:
                raise ValueError(f"Unknown opcode: 0x{opcode:02X}")

            # Simulate SPI bus transmission delay (request packet + response packet)
            total_bits = (len(packet) + len(response)) * 8
            effective_clocks = total_bits / self.bus_width
            bus_delay_ms = (effective_clocks / self.spi_clock_hz) * 1000.0

            t_flash = 0.0
            t_print = 0.0
            if opcode in (OPCODE_READ, OPCODE_WRITE, OPCODE_BLOCK_ERASE):
                t_flash = self.nor_storage.last_op_duration_ms
                t_print = self.nor_storage.last_print_duration_ms

            # Calculate total elapsed time as the exact mathematical sum of components to eliminate Python scheduling/IO jitter.
            # If the operation didn't touch flash, calculate actual Python execution time + bus delay.
            if opcode in (OPCODE_READ, OPCODE_WRITE, OPCODE_BLOCK_ERASE):
                elapsed_ms = t_flash + t_print + bus_delay_ms
            else:
                elapsed_ms = (time.perf_counter() - start_time) * 1000.0 + bus_delay_ms

            # Record the command for terminal display
            self.last_command = {
                "timestamp": timestamp,
                "opcode": opcode,
                "opcode_name": op_name,
                "address": address,
                "length": length,
                "spi_mode": self.spi_mode.upper(),
                "bus_width": self.bus_width,
                "status": "OK",
                "response_len": len(response),
                "elapsed_ms": elapsed_ms,
                "t_flash": t_flash,
                "t_print": t_print,
                "t_spi": bus_delay_ms,
                "packet": packet,
                "response": response,
            }

            # Terminal: print completion
            term.print_spi_response(len(response), "OK", elapsed_ms)
            if opcode in (OPCODE_READ, OPCODE_WRITE, OPCODE_BLOCK_ERASE):
                term.print_duration_breakdown(elapsed_ms, t_flash, t_print)

        except Exception as e:
            t_flash = 0.0
            t_print = 0.0
            if opcode in (OPCODE_READ, OPCODE_WRITE, OPCODE_BLOCK_ERASE):
                t_flash = getattr(self.nor_storage, "last_op_duration_ms", 0.0)
                t_print = getattr(self.nor_storage, "last_print_duration_ms", 0.0)
            
            # Use same timing model for consistency even in failure
            bus_delay_ms = getattr(self, "bus_delay_ms", 0.0)
            if opcode in (OPCODE_READ, OPCODE_WRITE, OPCODE_BLOCK_ERASE):
                elapsed_ms = t_flash + t_print + bus_delay_ms
            else:
                elapsed_ms = (time.perf_counter() - start_time) * 1000.0
                
            self.last_command = {
                "timestamp": timestamp,
                "opcode": opcode,
                "opcode_name": op_name,
                "address": address,
                "length": length,
                "spi_mode": self.spi_mode.upper(),
                "bus_width": self.bus_width,
                "status": f"ERROR: {e}",
                "response_len": 0,
                "elapsed_ms": elapsed_ms,
                "t_flash": t_flash,
                "t_print": t_print,
                "t_spi": bus_delay_ms,
                "packet": packet,
                "response": b"",
            }
            logger.error("SPI command error: %s", e)
            raise

        finally:
            # Always log the transaction
            if self.last_command:
                self.transaction_log.append(self.last_command)

        return response

    def _decode_opcode(self, opcode: int) -> str:
        """
        Decode an opcode byte to its human-readable name.

        Args:
            opcode: SPI opcode byte.

        Returns:
            Human-readable operation name.
        """
        return OPCODE_NAMES.get(opcode, f"UNKNOWN(0x{opcode:02X})")

    def get_last_command(self) -> dict | None:
        """
        Return information about the last processed SPI command.

        Returns:
            Dictionary with command details, or None if no commands processed yet.
        """
        return self.last_command

    def get_transaction_log(self, last_n: int | None = None) -> list[dict]:
        """
        Return the transaction log.

        Args:
            last_n: If specified, return only the last N transactions.

        Returns:
            List of transaction dictionaries.
        """
        if last_n is not None:
            return self.transaction_log[-last_n:]
        return list(self.transaction_log)

    def format_last_command(self) -> str:
        """
        Format the last command for terminal display.

        Returns:
            Formatted string showing the last command details.
        """
        cmd = self.last_command
        if cmd is None:
            return "Last Command: (none)"

        lines = [
            "Last Command:",
            f"  Opcode  : 0x{cmd['opcode']:02X} ({cmd['opcode_name']})",
        ]
        if cmd["address"] is not None:
            lines.append(f"  Address : 0x{cmd['address']:04X}")
        if cmd["length"] is not None:
            lines.append(f"  Length  : {cmd['length']}")
        lines.extend([
            f"  Mode    : {cmd['spi_mode']} ({cmd['bus_width']}-bit)",
            f"  Status  : {cmd['status']}",
            f"  Time    : {cmd['timestamp'].strftime('%H:%M:%S.%f')[:-3]}",
        ])
        return "\n".join(lines)
