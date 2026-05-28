# NOR Flash Memory Simulator with SPI & Streamlit GUI

A modular Python-based NOR Flash Memory Simulator that models the high-level functional behavior of a 64KB NOR Flash device. It features a complete SPI Master-Slave protocol architecture, simulated hardware latency, a terminal REPL mode, and a rich Streamlit Web GUI with visual hex views and timing breakdown statistics.

---

## Features

- **4-Layer SPI Stack**: Models clean decoupling between host applications, the SPI Master controller, the SPI Slave protocol decoder, and the underlying NOR storage array.
- **Realistic NOR Constraint Simulation**: Enforces real-world physical constraints (bits can only transition from `1` to `0` via programming). Writing to a non-erased region is performed via bitwise AND (`new = old & data`). An erase command is required to set bits back to `1` (`0xFF`).
- **Simulated Hardware Latencies**: Uses configurable delays for read, write, and block erase operations to simulate physical memory cell performance.
- **Configurable SPI Bus Widths**: Supports standard 1-bit **SPI**, 4-bit **QSPI**, and 8-bit **Octal SPI** modes, dynamically logging transmission speeds and clock cycle counts.
- **Console Aesthetics & Timing Breakdown**: Prints colored operation trace blocks to the terminal, separating commands clearly and showing exactly how long SPI clocking, flash memory programming, and terminal drawing (overhead) took.
- **Streamlit GUI**: Tabbed dashboard showing:
  - **Read**: Interactive memory reads from hex addresses.
  - **Write**: Space-separated hex page programming with readback validation.
  - **Erase**: Sector/block dropdown picker with safety warnings.
  - **Memory Viewer**: Full 64KB graphical hex table with block usage statistics.
  - **Transaction Log**: Chronological SPI command history with millisecond timing breakdowns.

---

## Directory Structure

```text
├── config.json           # Flash geometry, timing delays, and initial SPI mode
├── requirements.txt      # Python dependencies (numpy, streamlit, colorama)
├── main.py               # Terminal REPL entry point
├── gui/
│   └── app.py            # Streamlit Web GUI dashboard
├── storage/
│   └── norstorage.py     # NumPy-backed 4D flash array model with NOR constraints
├── spi/
│   ├── spi_master.py     # SPI Master packet builder and host bridge
│   └── spi_slave.py      # SPI Slave opcode decoder and transaction recorder
└── utils/
    ├── address.py        # Bidirectional address translation (linear <=> 4D hierarchy)
    ├── hexviewer.py      # Classic hex dump formatting
    └── terminal.py       # Colorama terminal color definitions & visual formatting
```

---

## Setup Instructions

### 1. Prerequisites
Ensure you have Python 3.10+ installed.

### 2. Install Dependencies
Install requirements in your environment:
```bash
pip install -r requirements.txt
```

---

## How to Run

### Option A: Interactive Terminal Mode
Run the command-line REPL to query and write to the device:
```bash
python main.py
```
**Available REPL Commands**:
- `r <hex_addr> <length>`: Read bytes (e.g., `r 0x0000 16`)
- `w <hex_addr> <hex_bytes...>`: Write space-separated hex bytes (e.g., `w 0x0000 AA BB CC DD`)
- `e <block_id>`: Erase a block (e.g., `e 0` to erase the first 16KB block)
- `d <hex_addr> <length>`: Dump memory region
- `m <mode>`: Set SPI mode (`spi`, `qspi`, `octal`)
- `s`: Show device status register
- `h`: Show command help
- `q`: Quit

### Option B: Streamlit Web GUI
Launch the web interface:
```bash
streamlit run gui/app.py
```
Then open `http://localhost:8501` in your browser.

---

## Configuration

Modify `config.json` to alter the simulator's settings:
```json
{
    "flash_size_kb": 64,
    "blocks": 4,
    "sectors_per_block": 4,
    "pages_per_sector": 16,
    "bytes_per_page": 256,
    "spi_mode": "qspi",
    "read_delay_ms": 10,
    "write_delay_ms": 100,
    "erase_delay_ms": 500
}
```
- Geometry: `4 blocks * 4 sectors * 16 pages * 256 bytes = 65,536 bytes (64 KB)`.
- Delays can be customized to change simulated latency.
