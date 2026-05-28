"""
NOR Flash Memory Simulator — Terminal Mode Entry Point.

Provides an interactive terminal interface for testing the NOR flash
simulator. Displays memory contents, SPI transaction info, and device
status. Accepts simple commands for read, write, and erase operations.
"""

import json
import logging
import os
import sys

# Configure logging before importing project modules
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("main")

from storage.norstorage import NORStorage
from spi.spi_slave import SPISlave
from spi.spi_master import SPIMaster


def load_config(config_path: str = "config.json") -> dict:
    """Load configuration from JSON file."""
    with open(config_path, "r") as f:
        return json.load(f)


def clear_screen():
    """Clear the terminal screen."""
    os.system("cls" if os.name == "nt" else "clear")


def print_header():
    """Print the simulator header banner."""
    print("=" * 60)
    print("       NOR Flash Memory Simulator — Terminal Mode")
    print("=" * 60)


def print_status(nor: NORStorage, slave: SPISlave):
    """Print the current device status and last SPI command."""
    print()
    print("─" * 60)

    # Last SPI command
    print(slave.format_last_command())

    # Device status
    status = nor.get_status()
    print()
    print("STATUS:")
    print(f"  BUSY      : {status['busy']}")
    print(f"  LAST OP   : {status['last_op']}")
    print(f"  SPI MODE  : {status['spi_mode'].upper()}")

    print("─" * 60)


def print_memory(nor: NORStorage, start: int = 0, length: int = 128):
    """Print a hex dump of the flash memory."""
    print()
    print(f"NOR Flash Contents (0x{start:04X} - 0x{start + length - 1:04X}):")
    print(nor.dump(start, length))


def print_help():
    """Print available commands."""
    print()
    print("Available Commands:")
    print("  r <hex_addr> <length>       — Read bytes")
    print("  w <hex_addr> <hex_bytes>    — Write bytes (space-separated hex)")
    print("  e <block_id>                — Erase block")
    print("  d <hex_addr> <length>       — Dump memory region")
    print("  s                           — Show status")
    print("  m <mode>                    — Set SPI mode (spi/qspi/octal)")
    print("  h                           — Show this help")
    print("  q                           — Quit")
    print()


def main():
    """Main entry point for terminal mode."""
    config = load_config()

    # Initialize the simulation stack
    nor = NORStorage(config)
    slave = SPISlave(nor, config.get("spi_mode", "spi"))
    master = SPIMaster(slave)

    clear_screen()
    print_header()
    print()
    print(f"Flash Size : {config['flash_size_kb']} KB")
    print(f"Blocks     : {config['blocks']}")
    print(f"Sectors/Blk: {config['sectors_per_block']}")
    print(f"Pages/Sec  : {config['pages_per_sector']}")
    print(f"Bytes/Page : {config['bytes_per_page']}")
    print(f"SPI Mode   : {config.get('spi_mode', 'spi').upper()}")
    print()

    print_help()

    # Default memory view
    view_start = 0
    view_length = 128

    while True:
        try:
            cmd_input = input("NOR> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting simulator.")
            break

        if not cmd_input:
            continue

        parts = cmd_input.split()
        cmd = parts[0].lower()

        try:
            if cmd == "q" or cmd == "quit" or cmd == "exit":
                print("Exiting simulator.")
                break

            elif cmd == "h" or cmd == "help":
                print_help()

            elif cmd == "r" or cmd == "read":
                if len(parts) < 3:
                    print("Usage: r <hex_addr> <length>")
                    continue
                address = int(parts[1], 16)
                length = int(parts[2])
                data = master.read(address, length)
                print(f"\nRead {length} bytes from 0x{address:04X}:")
                print(nor.dump(address, length))
                print_status(nor, slave)

            elif cmd == "w" or cmd == "write":
                if len(parts) < 3:
                    print("Usage: w <hex_addr> <hex_bytes...>")
                    continue
                address = int(parts[1], 16)
                data_bytes = bytes([int(b, 16) for b in parts[2:]])
                master.write(address, data_bytes)
                print(f"\nWrote {len(data_bytes)} bytes to 0x{address:04X}")
                print_status(nor, slave)
                print_memory(nor, address, max(len(data_bytes), 16))

            elif cmd == "e" or cmd == "erase":
                if len(parts) < 2:
                    print("Usage: e <block_id>")
                    continue
                block_id = int(parts[1])
                master.erase(block_id)
                print(f"\nBlock {block_id} erased")
                print_status(nor, slave)

            elif cmd == "d" or cmd == "dump":
                if len(parts) >= 3:
                    view_start = int(parts[1], 16)
                    view_length = int(parts[2])
                elif len(parts) == 2:
                    view_start = int(parts[1], 16)
                print_memory(nor, view_start, view_length)

            elif cmd == "s" or cmd == "status":
                print_status(nor, slave)

            elif cmd == "m" or cmd == "mode":
                if len(parts) < 2:
                    print("Usage: m <spi|qspi|octal>")
                    continue
                slave.set_spi_mode(parts[1])
                print(f"SPI mode set to: {parts[1].upper()}")

            else:
                print(f"Unknown command: '{cmd}'. Type 'h' for help.")

        except ValueError as e:
            print(f"Error: {e}")
        except Exception as e:
            print(f"Unexpected error: {e}")
            logger.exception("Command error")


if __name__ == "__main__":
    main()
