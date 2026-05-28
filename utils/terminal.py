"""
Terminal Output Utilities for NOR Flash Memory Simulator.

Provides colored and formatted terminal output using colorama
for cross-platform ANSI color support (especially on Windows).
"""

from colorama import init, Fore, Back, Style

# Initialize colorama for Windows ANSI support
init(autoreset=True)

# ─── Color Shortcuts ──────────────────────────────────────────────────

CYAN = Fore.CYAN
GREEN = Fore.GREEN
YELLOW = Fore.YELLOW
RED = Fore.RED
MAGENTA = Fore.MAGENTA
BLUE = Fore.BLUE
WHITE = Fore.WHITE
BRIGHT = Style.BRIGHT
RESET = Style.RESET_ALL
DIM = Style.DIM


# ─── Separator Lines ─────────────────────────────────────────────────

def separator_heavy():
    """Print a heavy separator line between commands."""
    print(f"{CYAN}{BRIGHT}{'=' * 70}{RESET}", flush=True)


def separator_light():
    """Print a light separator line within a command output."""
    print(f"{DIM}{'-' * 70}{RESET}", flush=True)


def separator_double():
    """Print a double separator line for major section breaks."""
    print(f"{CYAN}{BRIGHT}{'=' * 70}{RESET}", flush=True)


# ─── SPI Command Output ──────────────────────────────────────────────

def print_spi_header(opcode: int, op_name: str, spi_mode: str, bus_width: int, packet: bytes):
    """Print the SPI command header block."""
    print(flush=True)
    separator_double()
    print(f"  {MAGENTA}{BRIGHT}>> SPI COMMAND RECEIVED{RESET}", flush=True)
    separator_light()
    print(f"  {WHITE}Opcode  : {YELLOW}{BRIGHT}0x{opcode:02X}{RESET} ({CYAN}{op_name}{RESET})", flush=True)
    print(f"  {WHITE}Mode    : {GREEN}{spi_mode.upper()}{RESET} ({bus_width}-bit bus)", flush=True)
    print(f"  {WHITE}Packet  : {DIM}{' '.join(f'{b:02X}' for b in packet)}{RESET}", flush=True)
    separator_light()


def print_spi_response(response_len: int, status: str = "OK", elapsed_ms: float = None):
    """Print SPI response summary."""
    color = GREEN if status == "OK" else RED
    time_str = f" | Time: {elapsed_ms:.1f} ms" if elapsed_ms is not None else ""
    print(f"  {color}{BRIGHT}<< SPI RESPONSE: {response_len} byte(s) | Status: {status}{time_str}{RESET}", flush=True)


# ─── NOR Storage Operation Output ────────────────────────────────────

def print_read_header(address: int, length: int, elapsed_ms: float = None):
    """Print READ operation header."""
    time_str = f"  |  Time: {elapsed_ms:.1f} ms" if elapsed_ms is not None else ""
    print(f"\n  {BLUE}{BRIGHT}[READ]{RESET}  |  Address: {YELLOW}0x{address:04X}{RESET}  |  Length: {WHITE}{length}{RESET}{time_str}", flush=True)
    separator_light()


def print_write_header(address: int, length: int, elapsed_ms: float = None):
    """Print WRITE operation header."""
    time_str = f"  |  Time: {elapsed_ms:.1f} ms" if elapsed_ms is not None else ""
    print(f"\n  {GREEN}{BRIGHT}[WRITE]{RESET} |  Address: {YELLOW}0x{address:04X}{RESET}  |  Length: {WHITE}{length}{RESET}{time_str}", flush=True)
    separator_light()


def print_write_data(data: bytes, max_display: int = 32):
    """Print the raw data being written."""
    hex_str = " ".join(f"{b:02X}" for b in data[:max_display])
    suffix = "..." if len(data) > max_display else ""
    print(f"  {WHITE}Data written : {GREEN}{BRIGHT}{hex_str}{suffix}{RESET}", flush=True)


def print_write_warning(illegal_count: int):
    """Print NOR constraint warning."""
    print(f"  {YELLOW}{BRIGHT}[WARNING] {illegal_count} byte(s) had NOR constraint applied (new = old & data){RESET}", flush=True)


def print_erase_header(block_id: int, start_addr: int, end_addr: int, elapsed_ms: float = None):
    """Print ERASE operation header."""
    time_str = f"  |  Time: {elapsed_ms:.1f} ms" if elapsed_ms is not None else ""
    print(f"\n  {RED}{BRIGHT}[ERASE]{RESET} |  Block: {YELLOW}{block_id}{RESET}  |  Range: {YELLOW}0x{start_addr:04X}{RESET} - {YELLOW}0x{end_addr:04X}{RESET}{time_str}", flush=True)
    print(f"  {WHITE}All bytes set to {BRIGHT}0xFF{RESET}", flush=True)
    separator_light()


def print_memory_label(label: str = "Memory contents:"):
    """Print a label before a hex dump."""
    print(f"  {CYAN}{label}{RESET}", flush=True)


def print_hex_dump(hex_dump_str: str):
    """Print a hex dump with coloring — addresses in yellow, data in white."""
    for line in hex_dump_str.split("\n"):
        if " : " in line:
            parts = line.split(" : ", 1)
            addr = parts[0]
            rest = parts[1]
            # Split off ASCII column if present
            if "  |" in rest:
                hex_part, ascii_part = rest.rsplit("  |", 1)
                print(f"  {YELLOW}{addr}{RESET} : {WHITE}{BRIGHT}{hex_part}{RESET}  |{DIM}{ascii_part}{RESET}", flush=True)
            else:
                print(f"  {YELLOW}{addr}{RESET} : {WHITE}{BRIGHT}{rest}{RESET}", flush=True)
        else:
            print(f"  {line}", flush=True)


def print_status(busy: bool, last_op: str, spi_mode: str):
    """Print device status line."""
    separator_light()
    busy_str = f"{RED}{BRIGHT}True{RESET}" if busy else f"{GREEN}False{RESET}"
    print(f"  {DIM}STATUS:{RESET}  BUSY={busy_str}  LAST_OP={CYAN}{last_op}{RESET}  SPI_MODE={GREEN}{spi_mode.upper()}{RESET}", flush=True)


def print_end():
    """Print end separator for a command block."""
    separator_double()


def print_duration_breakdown(t_total: float, t_flash: float, t_print: float):
    """Print transaction execution duration breakdown."""
    t_spi = max(0.0, t_total - t_flash - t_print)
    
    # Calculate percentages
    pct_spi = (t_spi / t_total) * 100.0 if t_total > 0 else 0.0
    pct_flash = (t_flash / t_total) * 100.0 if t_total > 0 else 0.0
    pct_print = (t_print / t_total) * 100.0 if t_total > 0 else 0.0
    
    separator_light()
    print(f"  {CYAN}{BRIGHT}DURATION BREAKDOWN:{RESET}", flush=True)
    print(f"    {WHITE}- SPI Bus & Controller Overhead : {YELLOW}{t_spi:6.2f} ms{RESET} ({WHITE}{pct_spi:5.1f}%{RESET})", flush=True)
    print(f"    {WHITE}- NOR Flash Memory Operation    : {YELLOW}{t_flash:6.2f} ms{RESET} ({WHITE}{pct_flash:5.1f}%{RESET})", flush=True)
    print(f"    {WHITE}- Console Output Visualization  : {YELLOW}{t_print:6.2f} ms{RESET} ({WHITE}{pct_print:5.1f}%{RESET})", flush=True)
    print(f"  {CYAN}{BRIGHT}TOTAL TRANSACTION TIME            : {GREEN}{BRIGHT}{t_total:6.2f} ms{RESET} ({WHITE}100.0%{RESET})", flush=True)
