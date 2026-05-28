"""
NOR Flash Memory Simulator — Streamlit GUI.

Provides a rich web-based interface for interacting with the NOR flash
simulator. Supports read, write, and erase operations with real-time
memory visualization and SPI transaction logging.
"""

import json
import sys
import os
from datetime import datetime

import streamlit as st
import numpy as np

# Add project root to path so we can import project modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from storage.norstorage import NORStorage
from spi.spi_slave import SPISlave
from spi.spi_master import SPIMaster
from utils.hexviewer import format_hex_dump


# ─── Page Configuration ───────────────────────────────────────────────

st.set_page_config(
    page_title="NOR Flash Simulator",
    page_icon="💾",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ─── Custom CSS ────────────────────────────────────────────────────────

st.markdown("""
<style>
    /* Import Google Font */
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&family=Inter:wght@400;500;600;700&display=swap');

    /* Root variables */
    :root {
        --primary: #6C63FF;
        --primary-light: #8B83FF;
        --secondary: #00D9A6;
        --accent: #FF6B6B;
        --bg-dark: #0E1117;
        --bg-card: #1A1D23;
        --bg-card-hover: #22262E;
        --text-primary: #E8EAED;
        --text-secondary: #9AA0A6;
        --border: #2D3139;
        --success: #00D9A6;
        --error: #FF6B6B;
        --warning: #FFB74D;
    }

    /* Global font */
    html, body, [class*="st-"] {
        font-family: 'Inter', sans-serif;
    }

    /* Hex dump and code blocks */
    code, pre, .stCode {
        font-family: 'JetBrains Mono', monospace !important;
    }

    /* Main header styling */
    .main-header {
        background: linear-gradient(135deg, #6C63FF 0%, #4ECDC4 50%, #00D9A6 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        font-size: 2.2rem;
        font-weight: 700;
        margin-bottom: 0;
        letter-spacing: -0.5px;
    }

    .sub-header {
        color: var(--text-secondary);
        font-size: 0.95rem;
        margin-top: -8px;
        margin-bottom: 24px;
    }

    /* Card styling */
    .metric-card {
        background: linear-gradient(145deg, #1A1D23, #22262E);
        border: 1px solid #2D3139;
        border-radius: 12px;
        padding: 16px 20px;
        margin-bottom: 12px;
        transition: border-color 0.3s ease;
    }

    .metric-card:hover {
        border-color: #6C63FF;
    }

    .metric-label {
        color: #9AA0A6;
        font-size: 0.75rem;
        text-transform: uppercase;
        letter-spacing: 1.2px;
        font-weight: 600;
        margin-bottom: 4px;
    }

    .metric-value {
        color: #E8EAED;
        font-size: 1.3rem;
        font-weight: 700;
    }

    /* SPI mode badge */
    .spi-badge {
        display: inline-block;
        padding: 4px 14px;
        border-radius: 20px;
        font-size: 0.8rem;
        font-weight: 600;
        letter-spacing: 0.8px;
        text-transform: uppercase;
    }

    .spi-badge-spi {
        background: rgba(108, 99, 255, 0.15);
        color: #8B83FF;
        border: 1px solid rgba(108, 99, 255, 0.3);
    }

    .spi-badge-qspi {
        background: rgba(0, 217, 166, 0.15);
        color: #00D9A6;
        border: 1px solid rgba(0, 217, 166, 0.3);
    }

    .spi-badge-octal {
        background: rgba(255, 183, 77, 0.15);
        color: #FFB74D;
        border: 1px solid rgba(255, 183, 77, 0.3);
    }

    /* Operation status indicator */
    .status-indicator {
        display: inline-block;
        width: 8px;
        height: 8px;
        border-radius: 50%;
        margin-right: 8px;
        animation: pulse 2s ease-in-out infinite;
    }

    .status-ready {
        background: #00D9A6;
        box-shadow: 0 0 8px rgba(0, 217, 166, 0.4);
    }

    .status-busy {
        background: #FF6B6B;
        box-shadow: 0 0 8px rgba(255, 107, 107, 0.4);
        animation: pulse-busy 1s ease-in-out infinite;
    }

    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.6; }
    }

    @keyframes pulse-busy {
        0%, 100% { opacity: 1; transform: scale(1); }
        50% { opacity: 0.5; transform: scale(1.3); }
    }

    /* Transaction log entry */
    .tx-log-entry {
        background: #1A1D23;
        border-left: 3px solid #6C63FF;
        padding: 10px 14px;
        margin-bottom: 8px;
        border-radius: 0 8px 8px 0;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.82rem;
        line-height: 1.5;
    }

    .tx-log-entry.read-op { border-left-color: #6C63FF; }
    .tx-log-entry.write-op { border-left-color: #00D9A6; }
    .tx-log-entry.erase-op { border-left-color: #FF6B6B; }

    /* Result display */
    .result-success {
        background: rgba(0, 217, 166, 0.08);
        border: 1px solid rgba(0, 217, 166, 0.25);
        border-radius: 10px;
        padding: 16px;
        margin: 12px 0;
    }

    .result-error {
        background: rgba(255, 107, 107, 0.08);
        border: 1px solid rgba(255, 107, 107, 0.25);
        border-radius: 10px;
        padding: 16px;
        margin: 12px 0;
    }

    /* Hex dump display */
    .hex-dump {
        background: #0E1117;
        border: 1px solid #2D3139;
        border-radius: 10px;
        padding: 16px;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.85rem;
        line-height: 1.6;
        overflow-x: auto;
        color: #E8EAED;
    }

    /* Section header */
    .section-header {
        font-size: 1.1rem;
        font-weight: 600;
        color: #E8EAED;
        margin-bottom: 12px;
        padding-bottom: 8px;
        border-bottom: 1px solid #2D3139;
    }

    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background: #0E1117;
        border-right: 1px solid #2D3139;
    }

    /* Button styling */
    .stButton > button {
        border-radius: 8px;
        font-weight: 600;
        letter-spacing: 0.5px;
        transition: all 0.3s ease;
    }

    .stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(108, 99, 255, 0.3);
    }

    /* Divider */
    .divider {
        height: 1px;
        background: linear-gradient(90deg, transparent, #2D3139, transparent);
        margin: 20px 0;
    }
</style>
""", unsafe_allow_html=True)


# ─── Session State Initialization ──────────────────────────────────────

def init_session_state():
    """Initialize Streamlit session state with simulator components."""
    if "initialized" not in st.session_state:
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "config.json"
        )
        with open(config_path, "r") as f:
            config = json.load(f)

        nor = NORStorage(config)
        slave = SPISlave(nor, config.get("spi_mode", "spi"))
        master = SPIMaster(slave)

        st.session_state.config = config
        st.session_state.nor = nor
        st.session_state.slave = slave
        st.session_state.master = master
        st.session_state.messages = []  # GUI message log
        st.session_state.last_read_result = None
        st.session_state.last_write_result = None
        st.session_state.last_erase_result = None
        st.session_state.initialized = True


init_session_state()

# Shortcuts for session state
config = st.session_state.config
nor = st.session_state.nor
slave = st.session_state.slave
master = st.session_state.master


# ─── Helper Functions ──────────────────────────────────────────────────

def add_message(msg_type: str, text: str):
    """Add a message to the GUI log."""
    st.session_state.messages.append({
        "type": msg_type,
        "text": text,
        "time": datetime.now().strftime("%H:%M:%S"),
    })


def get_spi_badge_html(mode: str) -> str:
    """Return HTML for an SPI mode badge."""
    mode_lower = mode.lower()
    return f'<span class="spi-badge spi-badge-{mode_lower}">{mode.upper()}</span>'


def get_status_html(busy: bool) -> str:
    """Return HTML for a status indicator."""
    cls = "status-busy" if busy else "status-ready"
    text = "BUSY" if busy else "READY"
    return f'<span class="status-indicator {cls}"></span>{text}'


# ─── Sidebar ───────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown('<p class="main-header" style="font-size:1.5rem;">💾 NOR Flash Sim</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">SPI Communication Simulator</p>', unsafe_allow_html=True)

    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

    # Configuration display
    st.markdown('<p class="section-header">📋 Configuration</p>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Flash Size</div>
            <div class="metric-value">{config['flash_size_kb']} KB</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Blocks</div>
            <div class="metric-value">{config['blocks']}</div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Pages/Sector</div>
            <div class="metric-value">{config['pages_per_sector']}</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Bytes/Page</div>
            <div class="metric-value">{config['bytes_per_page']}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

    # SPI Mode selector
    st.markdown('<p class="section-header">🔌 SPI Mode</p>', unsafe_allow_html=True)

    current_mode = slave.spi_mode
    mode_options = ["spi", "qspi", "octal"]
    mode_labels = {
        "spi": "SPI (1-bit)",
        "qspi": "QSPI (4-bit)",
        "octal": "Octal SPI (8-bit)",
    }

    selected_mode = st.selectbox(
        "Bus Width",
        options=mode_options,
        format_func=lambda x: mode_labels[x],
        index=mode_options.index(current_mode),
        key="spi_mode_select",
        label_visibility="collapsed",
    )

    if selected_mode != current_mode:
        slave.set_spi_mode(selected_mode)
        add_message("info", f"SPI mode changed to {selected_mode.upper()}")
        st.rerun()

    st.markdown(get_spi_badge_html(slave.spi_mode), unsafe_allow_html=True)

    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

    # Timing info
    st.markdown('<p class="section-header">⏱️ Timing Delays</p>', unsafe_allow_html=True)
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Read Delay</div>
        <div class="metric-value">{config['read_delay_ms']} ms</div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Write Delay</div>
        <div class="metric-value">{config['write_delay_ms']} ms</div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Erase Delay</div>
        <div class="metric-value">{config['erase_delay_ms']} ms</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

    # Device status
    status = nor.get_status()
    st.markdown('<p class="section-header">📊 Device Status</p>', unsafe_allow_html=True)
    st.markdown(get_status_html(status["busy"]), unsafe_allow_html=True)
    st.markdown(f"**Last Op:** `{status['last_op']}`")


# ─── Main Content ─────────────────────────────────────────────────────

st.markdown('<p class="main-header">NOR Flash Memory Simulator</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">64KB NOR Flash with SPI Master-Slave Architecture</p>', unsafe_allow_html=True)

# ─── Operation Tabs ───────────────────────────────────────────────────

tab_read, tab_write, tab_erase, tab_memory, tab_log = st.tabs([
    "📖 Read", "✏️ Write", "🗑️ Erase", "🗺️ Memory Viewer", "📜 Transaction Log"
])

# ─── READ Tab ─────────────────────────────────────────────────────────

with tab_read:
    st.markdown('<p class="section-header">📖 Read Operation</p>', unsafe_allow_html=True)
    st.markdown("Read bytes from NOR flash memory at a specified address.")

    col_addr, col_len = st.columns(2)

    with col_addr:
        read_addr_str = st.text_input(
            "Address (hex)",
            value="0x0000",
            key="read_addr",
            help="Enter the starting address in hexadecimal (e.g., 0x1000)",
        )

    with col_len:
        read_length = st.number_input(
            "Length (bytes)",
            min_value=1,
            max_value=4096,
            value=64,
            step=16,
            key="read_len",
            help="Number of bytes to read (1-4096)",
        )

    if st.button("🔍 Read Data", key="btn_read", use_container_width=True, type="primary"):
        try:
            address = int(read_addr_str, 16)
            import time
            tx_count_before = len(slave.transaction_log)
            with st.spinner(f"Reading {read_length} bytes from 0x{address:04X}..."):
                data = master.read(address, read_length)

            tx_added = slave.transaction_log[tx_count_before:]
            t_flash = sum(tx.get("t_flash", 0.0) for tx in tx_added)
            t_print = sum(tx.get("t_print", 0.0) for tx in tx_added)
            t_spi = sum(tx.get("t_spi", 0.0) for tx in tx_added)
            elapsed_ms = t_flash + t_print + t_spi

            add_message("success", f"Read {read_length} bytes from 0x{address:04X} in {elapsed_ms:.1f} ms")

            hex_output = format_hex_dump(data, address)
            st.session_state.last_read_result = {
                "address": address,
                "length": len(data),
                "hex_dump": hex_output,
                "elapsed_ms": elapsed_ms,
                "t_flash": t_flash,
                "t_print": t_print,
                "t_spi": t_spi,
            }

        except ValueError as e:
            st.error(f"❌ Error: {e}")
            add_message("error", str(e))
            st.session_state.last_read_result = None
        except Exception as e:
            st.error(f"❌ Unexpected error: {e}")
            add_message("error", str(e))
            st.session_state.last_read_result = None

    # Display persisted read result
    if st.session_state.last_read_result:
        r = st.session_state.last_read_result
        st.success(f"✅ Successfully read {r['length']} bytes from address 0x{r['address']:04X} in {r['elapsed_ms']:.1f} ms")
        
        # Display breakdown metrics
        cols = st.columns(3)
        cols[0].metric("SPI Bus / Overhead", f"{r['t_spi']:.1f} ms")
        cols[1].metric("NOR Flash Latency", f"{r['t_flash']:.1f} ms")
        cols[2].metric("GUI Render / Console", f"{r['t_print']:.1f} ms")
        
        st.code(r["hex_dump"], language=None)

# ─── WRITE Tab ────────────────────────────────────────────────────────

with tab_write:
    st.markdown('<p class="section-header">✏️ Write (Page Program) Operation</p>', unsafe_allow_html=True)
    st.markdown(
        "Write data to NOR flash memory. "
        "**Note:** NOR flash only allows 1→0 bit transitions. Erase the block first to set bits back to 1."
    )

    write_addr_str = st.text_input(
        "Address (hex)",
        value="0x0000",
        key="write_addr",
        help="Enter the starting address in hexadecimal",
    )

    write_data_str = st.text_input(
        "Data (hex bytes, space-separated)",
        value="AA BB CC DD",
        key="write_data",
        help="Enter data bytes in hex, separated by spaces (e.g., AA BB CC DD EE FF)",
    )

    st.markdown(
        f"<small style='color: #9AA0A6;'>Preview: writing {len(write_data_str.split())} byte(s)</small>",
        unsafe_allow_html=True,
    )

    if st.button("💾 Write Data", key="btn_write", use_container_width=True, type="primary"):
        try:
            address = int(write_addr_str, 16)
            data_bytes = bytes([int(b, 16) for b in write_data_str.split()])

            import time
            tx_count_before = len(slave.transaction_log)
            with st.spinner(f"Programming {len(data_bytes)} bytes at 0x{address:04X}..."):
                master.write(address, data_bytes)

            tx_added = slave.transaction_log[tx_count_before:]
            t_flash = sum(tx.get("t_flash", 0.0) for tx in tx_added)
            t_print = sum(tx.get("t_print", 0.0) for tx in tx_added)
            t_spi = sum(tx.get("t_spi", 0.0) for tx in tx_added)
            elapsed_ms = t_flash + t_print + t_spi

            add_message("success", f"Wrote {len(data_bytes)} bytes to 0x{address:04X} in {elapsed_ms:.1f} ms")

            # Readback verification
            readback = master.read(address, max(len(data_bytes), 16))
            hex_output = format_hex_dump(readback, address)

            st.session_state.last_write_result = {
                "address": address,
                "length": len(data_bytes),
                "hex_dump": hex_output,
                "elapsed_ms": elapsed_ms,
                "t_flash": t_flash,
                "t_print": t_print,
                "t_spi": t_spi,
            }

        except ValueError as e:
            st.error(f"❌ Error: {e}")
            add_message("error", str(e))
            st.session_state.last_write_result = None
        except Exception as e:
            st.error(f"❌ Unexpected error: {e}")
            add_message("error", str(e))
            st.session_state.last_write_result = None

    # Display persisted write result
    if st.session_state.last_write_result:
        w = st.session_state.last_write_result
        st.success(f"✅ Successfully wrote {w['length']} bytes to address 0x{w['address']:04X} in {w['elapsed_ms']:.1f} ms")
        
        # Display breakdown metrics
        cols = st.columns(3)
        cols[0].metric("SPI Bus / Overhead", f"{w['t_spi']:.1f} ms")
        cols[1].metric("NOR Flash Latency", f"{w['t_flash']:.1f} ms")
        cols[2].metric("GUI Render / Console", f"{w['t_print']:.1f} ms")
        
        st.markdown("**Readback verification:**")
        st.code(w["hex_dump"], language=None)

# ─── ERASE Tab ────────────────────────────────────────────────────────

with tab_erase:
    st.markdown('<p class="section-header">🗑️ Block Erase Operation</p>', unsafe_allow_html=True)
    st.markdown(
        "Erase an entire block, resetting all bytes to `0xFF`. "
        "This is required before re-writing data to a block."
    )

    block_size = config["sectors_per_block"] * config["pages_per_sector"] * config["bytes_per_page"]

    erase_block = st.selectbox(
        "Select Block",
        options=list(range(config["blocks"])),
        format_func=lambda b: (
            f"Block {b}  —  "
            f"0x{b * block_size:04X} - 0x{(b + 1) * block_size - 1:04X}  "
            f"({block_size // 1024} KB)"
        ),
        key="erase_block",
    )

    st.warning(
        f"⚠️ This will erase **all {block_size:,} bytes** in Block {erase_block} "
        f"(addresses 0x{erase_block * block_size:04X} - 0x{(erase_block + 1) * block_size - 1:04X})"
    )

    if st.button("🗑️ Erase Block", key="btn_erase", use_container_width=True, type="primary"):
        try:
            import time
            tx_count_before = len(slave.transaction_log)
            with st.spinner(f"Erasing block {erase_block}..."):
                master.erase(erase_block)

            tx_added = slave.transaction_log[tx_count_before:]
            t_flash = sum(tx.get("t_flash", 0.0) for tx in tx_added)
            t_print = sum(tx.get("t_print", 0.0) for tx in tx_added)
            t_spi = sum(tx.get("t_spi", 0.0) for tx in tx_added)
            elapsed_ms = t_flash + t_print + t_spi

            add_message("success", f"Erased block {erase_block} in {elapsed_ms:.1f} ms")

            # Verify the erased area (first 128 bytes)
            erase_start = erase_block * block_size
            verify_data = master.read(erase_start, 128)
            hex_output = format_hex_dump(verify_data, erase_start)

            st.session_state.last_erase_result = {
                "block_id": erase_block,
                "hex_dump": hex_output,
                "erase_start": erase_start,
                "elapsed_ms": elapsed_ms,
                "t_flash": t_flash,
                "t_print": t_print,
                "t_spi": t_spi,
            }

        except ValueError as e:
            st.error(f"❌ Error: {e}")
            add_message("error", str(e))
            st.session_state.last_erase_result = None
        except Exception as e:
            st.error(f"❌ Unexpected error: {e}")
            add_message("error", str(e))
            st.session_state.last_erase_result = None

    # Display persisted erase result
    if st.session_state.last_erase_result:
        er = st.session_state.last_erase_result
        st.success(f"✅ Block {er['block_id']} erased successfully in {er['elapsed_ms']:.1f} ms — all bytes set to 0xFF")
        
        # Display breakdown metrics
        cols = st.columns(3)
        cols[0].metric("SPI Bus / Overhead", f"{er['t_spi']:.1f} ms")
        cols[1].metric("NOR Flash Latency", f"{er['t_flash']:.1f} ms")
        cols[2].metric("GUI Render / Console", f"{er['t_print']:.1f} ms")
        
        st.markdown("**Verification (first 128 bytes):**")
        st.code(er["hex_dump"], language=None)

# ─── MEMORY VIEWER Tab ───────────────────────────────────────────────

with tab_memory:
    st.markdown('<p class="section-header">🗺️ Memory Viewer</p>', unsafe_allow_html=True)
    st.markdown("Browse the full 64KB NOR flash memory contents.")

    block_size = config["sectors_per_block"] * config["pages_per_sector"] * config["bytes_per_page"]

    view_col1, view_col2 = st.columns(2)
    with view_col1:
        view_block = st.selectbox(
            "Block",
            options=list(range(config["blocks"])),
            format_func=lambda b: f"Block {b} (0x{b * block_size:04X})",
            key="view_block",
        )
    with view_col2:
        view_size = st.selectbox(
            "View Size",
            options=[64, 128, 256, 512, 1024],
            index=2,
            format_func=lambda s: f"{s} bytes",
            key="view_size",
        )

    view_start = view_block * block_size

    if st.button("🔄 Refresh", key="btn_refresh_mem", use_container_width=True):
        pass  # Simply re-renders

    # Read and display memory
    mem_data = bytearray()
    for i in range(view_size):
        from utils.address import linear_to_hierarchy
        try:
            b, s, p, o = linear_to_hierarchy(view_start + i, config)
            mem_data.append(int(nor.norarray[b, s, p, o]))
        except ValueError:
            break

    hex_output = format_hex_dump(bytes(mem_data), view_start)
    st.code(hex_output, language=None)

    # Memory statistics for this block
    block_data = nor.norarray[view_block].flatten()
    total_bytes = len(block_data)
    erased_bytes = int(np.sum(block_data == 0xFF))
    programmed_bytes = total_bytes - erased_bytes
    usage_pct = (programmed_bytes / total_bytes) * 100

    stat_cols = st.columns(4)
    with stat_cols[0]:
        st.metric("Block Size", f"{total_bytes:,} B")
    with stat_cols[1]:
        st.metric("Erased (0xFF)", f"{erased_bytes:,} B")
    with stat_cols[2]:
        st.metric("Programmed", f"{programmed_bytes:,} B")
    with stat_cols[3]:
        st.metric("Usage", f"{usage_pct:.1f}%")

# ─── TRANSACTION LOG Tab ─────────────────────────────────────────────

with tab_log:
    st.markdown('<p class="section-header">📜 SPI Transaction Log</p>', unsafe_allow_html=True)

    transactions = slave.get_transaction_log()

    if not transactions:
        st.info("No SPI transactions recorded yet. Perform a read, write, or erase operation to see logs.")
    else:
        st.markdown(f"**Total transactions:** {len(transactions)}")

        # Show recent transactions (newest first)
        for tx in reversed(transactions[-50:]):
            op_class = "read-op"
            if "WRITE" in tx.get("opcode_name", ""):
                op_class = "write-op"
            elif "ERASE" in tx.get("opcode_name", ""):
                op_class = "erase-op"

            addr_str = f"0x{tx['address']:04X}" if tx.get("address") is not None else "N/A"
            len_str = str(tx.get("length", "N/A"))
            
            t_flash_val = tx.get("t_flash", 0.0)
            t_print_val = tx.get("t_print", 0.0)
            t_spi_val = max(0.0, tx.get("elapsed_ms", 0.0) - t_flash_val - t_print_val)
            
            time_str = f"{tx['elapsed_ms']:.1f} ms (SPI: {t_spi_val:.1f}ms, Flash: {t_flash_val:.1f}ms, Print: {t_print_val:.1f}ms)" if tx.get("elapsed_ms") is not None else "N/A"

            st.markdown(f"""
            <div class="tx-log-entry {op_class}">
                <strong>{tx['timestamp'].strftime('%H:%M:%S.%f')[:-3]}</strong> &nbsp;│&nbsp;
                <strong>0x{tx['opcode']:02X}</strong> {tx['opcode_name']} &nbsp;│&nbsp;
                Addr: {addr_str} &nbsp;│&nbsp;
                Len: {len_str} &nbsp;│&nbsp;
                Mode: {tx['spi_mode']} ({tx['bus_width']}-bit) &nbsp;│&nbsp;
                Time: {time_str} &nbsp;│&nbsp;
                {tx['status']}
            </div>
            """, unsafe_allow_html=True)

        if st.button("🧹 Clear Log", key="btn_clear_log"):
            slave.transaction_log.clear()
            st.rerun()
