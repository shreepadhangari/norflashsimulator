# Project Report: Architecture & Implementation of a NOR Flash Memory Simulator

## 1. Introduction & Project Objective

The objective of this project is to develop a functional, modular, and educational Python-based simulator for a **64KB NOR Flash memory device** coupled with a simulated **SPI (Serial Peripheral Interface) communication protocol stack**. 

This simulator models the functional behavior of a NOR flash device, including the physical constraints of NOR memory cells (such as write-propagation rules) and simulated hardware latencies. The interface is visualized through both a command-line REPL and an interactive Streamlit GUI. It is designed for architecture exploration, firmware debugging support, and educational visualization of memory operations.

---

## 2. System Architecture

The project is structured around a decoupled **4-Layer Architecture** that mimics a real physical system. This ensures that changing the user interface does not affect the communication protocol, and modifying the protocol details does not affect the core memory array logic.

```mermaid
graph TD
    UI[Streamlit GUI app.py] -->|High-level requests| Master[SPI Master spi_master.py]
    REPL[Terminal REPL main.py] -->|High-level requests| Master
    Master -->|Serialized SPI Packet bytes| Slave[SPI Slave spi_slave.py]
    Slave -->|Decoded Opcodes & Params| Storage[NOR Storage norstorage.py]
    Storage -->|Bidirectional Translation| Addr[Address Translator address.py]
    Storage -->|State Visualization| Term[Terminal Output Utility terminal.py]
```

### 2.1 The Four Layers
1. **User Interface Layer (`main.py` & `gui/app.py`)**: Displays the memory grid, records transactions, and provides buttons/inputs for users.
2. **SPI Master Controller (`spi/spi_master.py`)**: Emulates the host microcontroller's SPI controller. It takes high-level operations (e.g., "Write AA BB to address 0x0000") and encodes them into standard SPI transaction packets.
3. **SPI Slave Interface (`spi/spi_slave.py`)**: Emulates the NOR flash on-chip controller. It receives serialized byte packets, parses opcodes, checks packet integrity, simulates clock-cycle transfer overhead, and dispatches requests to the memory array.
4. **NOR Storage Core (`storage/norstorage.py`)**: Simulates the physical memory storage array, enforcing page-boundary constraints, timing delays, and NOR-cell write/erase behaviors.

---

## 3. Core Component Implementation Details

### 3.1 Bidirectional Address Translation (`utils/address.py`)
To emulate memory organization, the 64KB array is physically arranged as a **4D coordinate system**:
$$\text{Block} \rightarrow \text{Sector} \rightarrow \text{Page} \rightarrow \text{Byte Offset}$$

The simulator configuration defines:
- **Blocks**: 4
- **Sectors per Block**: 4
- **Pages per Sector**: 16
- **Bytes per Page**: 256
- Total Capacity: $4 \times 4 \times 16 \times 256 = 65,536 \text{ bytes (64 KB)}$

#### Math Formula:
Given a linear flat address $A \in [0, 65535]$:
$$\text{Block Size } (S_B) = \text{Sectors/Block} \times \text{Pages/Sector} \times \text{Bytes/Page} = 16,384 \text{ B}$$
$$\text{Sector Size } (S_S) = \text{Pages/Sector} \times \text{Bytes/Page} = 4,096 \text{ B}$$
$$\text{Page Size } (S_P) = \text{Bytes/Page} = 256 \text{ B}$$

The coordinates are extracted using integer division and modulo math:
$$\text{Block} = A \div S_B$$
$$\text{Sector} = (A \pmod{S_B}) \div S_S$$
$$\text{Page} = (A \pmod{S_S}) \div S_P$$
$$\text{Offset} = A \pmod{S_P}$$

Conversely, the linear address is reconstructed as:
$$\text{Linear Address} = (\text{Block} \times S_B) + (\text{Sector} \times S_S) + (\text{Page} \times S_P) + \text{Offset}$$

---

### 3.2 NumPy-Backed Storage Array & NOR Constraints (`storage/norstorage.py`)
The memory contents are managed via a multidimensional NumPy array initialized to `0xFF` (representing the erased state of a floating-gate transistor where the gate holds no trapped electrons):
```python
self.norarray = np.full((blocks, sectors, pages, bytes), 0xFF, dtype=np.uint8)
```

#### The NOR Bit-Transition Rule:
NOR flash cells can only transition from charge-state **1 to 0** during programming. Changing a bit from **0 to 1** requires exposing the entire block to high voltage, resetting all cells back to `1` (`0xFF`).

To program incoming bytes, the simulator performs a bitwise **AND** between the existing flash byte and the new byte:
$$\text{New Value} = \text{Old Value} \ \& \ \text{Incoming Byte}$$

If $\text{New Value} \neq \text{Incoming Byte}$, it implies that the write operation attempted an illegal `0` to `1` transition. The simulator programs the cell using the AND result anyway (matching real hardware behavior) and logs a warning:
```python
new_value = old_value & incoming_byte
if new_value != incoming_byte:
    illegal_transitions += 1
```

---

### 3.3 SPI Protocol Packets & Physical Bus Timing (`spi/`)
The Master and Slave exchange bytes using standard commands:

| Command | Opcode | Packet Structure | Description |
|---|---|---|---|
| **READ** | `0x03` | `[0x03][Addr MSB][Addr Mid][Addr LSB][Length]` | Reads up to 256 bytes |
| **WRITE** | `0x02` | `[0x02][Addr MSB][Addr Mid][Addr LSB][Data_0 ... Data_N]` | Programs bytes |
| **ERASE** | `0xD8` | `[0xD8][Block ID]` | Erases block (sets to 0xFF) |
| **READ STATUS** | `0x05` | `[0x05]` | Returns busy flags |

#### Physical Bus Timing Simulation:
Bus timings are calculated dynamically using the configured SPI frequency (`spi_clock_mhz` in `config.json`) and the physical bus width parameters for standard SPI, QSPI, and Octal SPI:

1. **Clocks Per Byte**:
   - **Standard SPI**: 1-bit bus $\rightarrow$ 8 clock cycles per byte.
   - **QSPI**: 4-bit bus $\rightarrow$ 2 clock cycles per byte.
   - **Octal SPI**: 8-bit bus $\rightarrow$ 1 clock cycle per byte.

2. **Transmission Time Formula**:
   $$\text{Transfer Bits} = (\text{Command Packet Size} + \text{Response Packet Size}) \times 8$$
   $$\text{Clock Cycles} = \frac{\text{Transfer Bits}}{\text{Bus Width}}$$
   $$\text{Simulated Bus Delay (seconds)} = \frac{\text{Clock Cycles}}{\text{SPI Clock Frequency (Hz)}}$$

To implement this timing model, the `SPISlave` applies a `time.sleep(bus_delay)` during transaction processing. Consequently, larger read/write requests show noticeable and mathematically accurate transmission latency differences depending on the bus mode selected.

---

## 4. Execution Timing & Latency Breakdown Model

To visualize and debug performance bottlenecks, the simulator splits the total execution time of every operation into three subtasks using high-precision timers (`time.perf_counter()`):

1. **SPI Bus & Controller Overhead ($t_{\text{SPI}}$)**:
   The time spent clocking the bits over the bus wires (simulated using the formula in section 3.3) plus actual master-slave packet serialization and protocol decode overhead.
2. **Flash Operation Latency ($t_{\text{Flash}}$)**:
   The pure physical operational latency of the memory cell arrays (emulated via `time.sleep` based on `config.json`) plus actual cell-write array updates.
3. **Console Logging & Rendering ($t_{\text{Print}}$)**:
   The CPU time spent formatting the hex grid layout, color-coding log details, and printing updates to the screen.

#### Calculation:
$$t_{\text{Total}} = t_{\text{SPI}} + t_{\text{Flash}} + t_{\text{Print}}$$
$$t_{\text{SPI}} = \max(0, t_{\text{Total}} - t_{\text{Flash}} - t_{\text{Print}})$$

These breakdowns are presented dynamically as stats (e.g. `Time: 101.3 ms (SPI: 0.2ms, Flash: 100.4ms, Print: 0.8ms)`) in both command-line trace blocks and interactive Streamlit metric tables.

---

## 5. User Interface Implementations

### 5.1 Interactive Terminal REPL (`main.py`)
A fast interactive terminal loop that reads user input commands (e.g., `r 0x0000 16`), calls the SPI Master layer, formats results in colorized blocks, and displays color-coded operation results. Separators prevent visual clutter on Windows consoles.

### 5.2 Streamlit Dashboard (`gui/app.py`)
An interactive dashboard optimized for state preservation.
- **State Management**: Uses Streamlit's `st.session_state` to persist the simulated NOR array and SPI controller instances across application reruns (preventing reinstantiation upon user interactions).
- **Tab Layout**:
  - **Read/Write/Erase Panels**: Forms with validation checking.
  - **Memory Viewer**: Provides a clean look at the memory grid with metrics showing erased capacity vs programmed capacity.
  - **Transaction History**: Displays detailed logs of all actions with timing breakdowns showing subtask allocations.
