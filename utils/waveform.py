"""
SPI Waveform Visualization Module for NOR Flash Memory Simulator.

Generates inline SVG timing diagrams showing CLK, CS#, MOSI/MISO (or
DATA bus) signal activity for SPI transactions.  Supports Standard SPI
(1-bit), QSPI (4-bit), and Octal SPI (8-bit) bus-width rendering.

No external dependencies — produces raw SVG markup strings that can be
embedded directly in Streamlit via st.markdown(unsafe_allow_html=True).
"""

# ─── Theme Colors (matching Streamlit dark theme) ─────────────────────

_CLK_COLOR  = "#6C63FF"   # Primary purple
_CS_COLOR   = "#FF6B6B"   # Accent red
_MOSI_COLOR = "#00D9A6"   # Secondary green
_MISO_COLOR = "#FFB74D"   # Amber / orange
_BG_COLOR   = "#0E1117"   # Dark background
_GRID_COLOR = "#1A1D23"   # Subtle grid lines
_TEXT_COLOR  = "#9AA0A6"   # Label text
_PHASE_COLORS = {
    "OPCODE": "#8B83FF",
    "ADDR":   "#4ECDC4",
    "LEN":    "#6C63FF",
    "DATA":   "#00D9A6",
    "BLOCK":  "#FFB74D",
    "RESP":   "#FFB74D",
}

# ─── Layout Constants ─────────────────────────────────────────────────

_LABEL_W   = 80    # left margin for signal-name labels
_SIG_H     = 28    # height of each signal trace
_SIG_GAP   = 14    # vertical gap between signal rows
_MARGIN_T  = 10    # top margin
_MARGIN_R  = 20    # right margin
_MARGIN_B  = 12    # bottom margin
_PHASE_H   = 22    # height of phase-label row
_IDLE      = 2     # idle clock cycles drawn before and after active region


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Public API
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def generate_waveform_svg(
    transaction: dict,
    max_display_bytes: int | None = None,
) -> str:
    """Generate an SVG timing diagram for a single SPI transaction.

    Args:
        transaction: Dict from ``SPISlave.transaction_log`` containing at
            minimum ``packet``, ``response``, ``bus_width``, ``opcode``.
        max_display_bytes: Cap on data-payload bytes to render.  When
            *None* the limit is auto-scaled per bus mode so the diagram
            stays a reasonable width.

    Returns:
        SVG markup string ready for embedding in HTML.
    """
    packet   = bytes(transaction.get("packet", b""))
    response = bytes(transaction.get("response", b""))
    bus_width = transaction.get("bus_width", 1)
    opcode    = transaction.get("opcode", 0)

    if not packet:
        return (
            '<div style="color:#9AA0A6; text-align:center; padding:32px; '
            "font-family:Inter,sans-serif; font-size:0.9rem;\">"
            "No packet data recorded for this transaction.<br>"
            '<small style="opacity:0.5;">Transactions recorded before the '
            "waveform update do not contain raw packet bytes.</small></div>"
        )

    # ── Adaptive parameters per bus width ──────────────────────────────
    if bus_width == 1:
        cw = 20           # clock-cell width (px): narrow for 1-bit mode
        default_max = 8
    elif bus_width == 4:
        cw = 34
        default_max = 14
    else:                 # bus_width == 8 (Octal)
        cw = 42
        default_max = 16

    max_bytes = max_display_bytes if max_display_bytes is not None else default_max

    # ── Truncate long payloads ─────────────────────────────────────────
    dp, dr, truncated = _truncate(packet, response, opcode, max_bytes)

    # ── Clock maths ────────────────────────────────────────────────────
    cpb     = 8 // bus_width          # clocks per byte
    pkt_clk = len(dp) * cpb
    rsp_clk = len(dr) * cpb
    act_clk = pkt_clk + rsp_clk

    if act_clk == 0:
        return '<div style="color:#9AA0A6;padding:20px;">Empty transaction.</div>'

    tot_clk = _IDLE + act_clk + _IDLE

    # ── Vertical layout positions ──────────────────────────────────────
    y_ph  = _MARGIN_T
    y_clk = y_ph  + _PHASE_H + 6
    y_cs  = y_clk + _SIG_H + _SIG_GAP
    y_mo  = y_cs  + _SIG_H + _SIG_GAP
    y_mi  = y_mo  + _SIG_H + _SIG_GAP
    svg_h = y_mi  + _SIG_H + _MARGIN_B
    svg_w = _LABEL_W + tot_clk * cw + _MARGIN_R

    x0 = _LABEL_W                    # x-origin (first clock slot)
    xa = x0 + _IDLE * cw             # x where active clocks begin

    parts: list[str] = []

    # ── Background ─────────────────────────────────────────────────────
    parts.append(
        f'<rect width="{svg_w}" height="{svg_h}" '
        f'fill="{_BG_COLOR}" rx="8"/>'
    )

    # Subtle active-region highlight
    aw = act_clk * cw
    parts.append(
        f'<rect x="{xa}" y="{y_clk - 4}" width="{aw}" '
        f'height="{y_mi + _SIG_H - y_clk + 8}" '
        f'fill="#FFFFFF" fill-opacity="0.015" rx="4"/>'
    )

    # ── Vertical grid lines ────────────────────────────────────────────
    for i in range(act_clk + 1):
        gx = xa + i * cw
        parts.append(
            f'<line x1="{gx}" y1="{y_clk}" x2="{gx}" '
            f'y2="{y_mi + _SIG_H}" stroke="{_GRID_COLOR}" '
            f'stroke-width="0.5"/>'
        )

    # ── Phase divider (command ↔ response boundary) ────────────────────
    if pkt_clk > 0 and rsp_clk > 0:
        dx = xa + pkt_clk * cw
        parts.append(
            f'<line x1="{dx}" y1="{y_ph}" x2="{dx}" '
            f'y2="{y_mi + _SIG_H}" stroke="#4ECDC4" '
            f'stroke-width="1" stroke-dasharray="5,3" opacity="0.3"/>'
        )

    # ── Phase labels ───────────────────────────────────────────────────
    phases = _get_phases(opcode, len(dp), len(dr))
    _add_phase_labels(parts, phases, xa, y_ph, cw, cpb)

    # ── Signal name labels (left margin) ───────────────────────────────
    mo_label = "MOSI" if bus_width == 1 else "DATA \u2192"
    mi_label = "MISO" if bus_width == 1 else "DATA \u2190"
    parts.append(_label("CLK",    8, y_clk + _SIG_H // 2 + 4, _CLK_COLOR))
    parts.append(_label("CS#",    8, y_cs  + _SIG_H // 2 + 4, _CS_COLOR))
    parts.append(_label(mo_label, 8, y_mo  + _SIG_H // 2 + 4, _MOSI_COLOR))
    parts.append(_label(mi_label, 8, y_mi  + _SIG_H // 2 + 4, _MISO_COLOR))

    # ── CLK signal ─────────────────────────────────────────────────────
    _add_clock(parts, act_clk, _IDLE, _IDLE, x0, y_clk, cw, _SIG_H)

    # ── CS# signal ─────────────────────────────────────────────────────
    _add_cs(parts, act_clk, _IDLE, _IDLE, x0, y_cs, cw, _SIG_H)

    # ── MOSI / DATA→ ──────────────────────────────────────────────────
    if bus_width == 1:
        bits = _to_bits(dp)
        _add_digital(
            parts, bits, _IDLE, rsp_clk + _IDLE,
            x0, y_mo, cw, _SIG_H, _MOSI_COLOR,
        )
    else:
        vals = _to_bus_vals(dp, bus_width)
        _add_bus(
            parts, vals, _IDLE, rsp_clk + _IDLE,
            x0, y_mo, cw, _SIG_H, _MOSI_COLOR,
        )

    # ── MISO / DATA← ──────────────────────────────────────────────────
    if bus_width == 1:
        bits = _to_bits(dr)
        _add_digital(
            parts, bits, _IDLE + pkt_clk, _IDLE,
            x0, y_mi, cw, _SIG_H, _MISO_COLOR,
        )
    else:
        vals = _to_bus_vals(dr, bus_width)
        _add_bus(
            parts, vals, _IDLE + pkt_clk, _IDLE,
            x0, y_mi, cw, _SIG_H, _MISO_COLOR,
        )

    # ── Truncation marker ─────────────────────────────────────────────
    if truncated:
        parts.append(
            f'<text x="{svg_w - _MARGIN_R}" y="{svg_h // 2}" '
            f'fill="{_TEXT_COLOR}" font-size="16" font-weight="bold" '
            f'text-anchor="end">\u22EF</text>'
        )

    # ── Assemble final SVG ─────────────────────────────────────────────
    content = "\n".join(parts)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{svg_w}" height="{svg_h}" '
        f'viewBox="0 0 {svg_w} {svg_h}" '
        f"style=\"font-family:'JetBrains Mono',monospace; display:block;\">\n"
        f"{content}\n</svg>"
    )


def generate_legend_html() -> str:
    """Return an HTML legend bar describing the waveform signal colours."""
    items = [
        (_CLK_COLOR,  "CLK \u2014 Clock"),
        (_CS_COLOR,   "CS# \u2014 Chip Select"),
        (_MOSI_COLOR, "MOSI / DATA\u2192"),
        (_MISO_COLOR, "MISO / DATA\u2190"),
    ]
    spans = "".join(
        f'<span style="display:inline-flex;align-items:center;gap:6px;'
        f'margin-right:20px;">'
        f'<span style="display:inline-block;width:10px;height:10px;'
        f'border-radius:2px;background:{c};"></span>'
        f'<span style="color:#E8EAED;font-size:0.82rem;">{lbl}</span></span>'
        for c, lbl in items
    )
    return (
        f'<div style="display:flex;flex-wrap:wrap;gap:8px;padding:10px 14px;'
        f'background:#1A1D23;border:1px solid #2D3139;border-radius:8px;'
        f"margin:8px 0;font-family:'JetBrains Mono',monospace;\">{spans}</div>"
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Internal helpers
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _truncate(packet: bytes, response: bytes, opcode: int, max_bytes: int):
    """Truncate data payload, keeping the command header intact.

    Returns:
        (display_packet, display_response, was_truncated)
    """
    trunc = False
    if opcode == 0x03:          # READ: pkt = [op,A2,A1,A0,len]
        dp = packet[:5]
        dr = response[:max_bytes]
        trunc = len(response) > max_bytes
    elif opcode == 0x02:        # WRITE: pkt = [op,A2,A1,A0,D0..Dn]
        dp = packet[:4 + max_bytes]
        dr = response
        trunc = len(packet) > 4 + max_bytes
    else:                       # ERASE / STATUS / generic
        dp = packet
        dr = response[:max_bytes]
        trunc = len(response) > max_bytes
    return bytes(dp), bytes(dr), trunc


def _to_bits(data: bytes) -> list[int]:
    """Bytes -> flat list of ints (MSB first per byte)."""
    return [((b >> (7 - i)) & 1) for b in data for i in range(8)]


def _to_bus_vals(data: bytes, bus_width: int) -> list[int]:
    """Bytes -> per-clock bus values (nibbles for QSPI, bytes for Octal)."""
    vals: list[int] = []
    for byte in data:
        if bus_width >= 8:
            vals.append(byte)
        elif bus_width == 4:
            vals.append((byte >> 4) & 0xF)
            vals.append(byte & 0xF)
        else:  # fallback — shouldn't happen for supported modes
            for i in range(7, -1, -1):
                vals.append((byte >> i) & 1)
    return vals


def _get_phases(opcode: int, pkt_len: int, rsp_len: int):
    """Return list of ``(phase_name, byte_count)`` tuples."""
    phases: list[tuple[str, int]] = []

    if opcode == 0x03:  # READ
        phases.append(("OPCODE", min(1, pkt_len)))
        rem = max(0, pkt_len - 1)
        a = min(3, rem)
        if a:
            phases.append(("ADDR", a))
            rem -= a
        if rem > 0:
            phases.append(("LEN", rem))
        if rsp_len > 0:
            phases.append(("RESP", rsp_len))

    elif opcode == 0x02:  # WRITE
        phases.append(("OPCODE", min(1, pkt_len)))
        rem = max(0, pkt_len - 1)
        a = min(3, rem)
        if a:
            phases.append(("ADDR", a))
            rem -= a
        if rem > 0:
            phases.append(("DATA", rem))
        if rsp_len > 0:
            phases.append(("RESP", rsp_len))

    elif opcode == 0xD8:  # ERASE
        phases.append(("OPCODE", min(1, pkt_len)))
        rem = max(0, pkt_len - 1)
        if rem > 0:
            phases.append(("BLOCK", rem))
        if rsp_len > 0:
            phases.append(("RESP", rsp_len))

    else:  # READ_STATUS / generic
        phases.append(("OPCODE", min(1, pkt_len)))
        rem = max(0, pkt_len - 1)
        if rem > 0:
            phases.append(("DATA", rem))
        if rsp_len > 0:
            phases.append(("RESP", rsp_len))

    return phases


# ── Label helpers ─────────────────────────────────────────────────────

def _label(name: str, x: float, y: float, color: str) -> str:
    return (
        f'<text x="{x}" y="{y}" fill="{color}" '
        f'font-size="11" font-weight="600">{name}</text>'
    )


def _add_phase_labels(
    parts: list[str],
    phases: list[tuple[str, int]],
    xa: float,
    y: float,
    cw: int,
    cpb: int,
):
    """Add coloured phase-label rectangles above the waveform."""
    x = xa
    rh = 18
    ry = y + 2
    for name, n_bytes in phases:
        w = n_bytes * cpb * cw
        if w <= 0:
            continue
        color = _PHASE_COLORS.get(name, _TEXT_COLOR)
        parts.append(
            f'<rect x="{x}" y="{ry}" width="{w}" height="{rh}" rx="4" '
            f'fill="{color}" fill-opacity="0.12" stroke="{color}" '
            f'stroke-width="0.8" stroke-opacity="0.35"/>'
        )
        fs = 9 if w > 38 else 7
        parts.append(
            f'<text x="{x + w / 2}" y="{ry + rh / 2 + 4}" '
            f'text-anchor="middle" fill="{color}" font-size="{fs}" '
            f'font-weight="600">{name}</text>'
        )
        x += w


# ── Signal renderers ─────────────────────────────────────────────────

def _add_clock(
    parts: list[str],
    n_active: int,
    idle_pre: int,
    idle_post: int,
    x0: float,
    y: float,
    cw: int,
    sh: int,
):
    """Add CLK square-wave SVG path."""
    yh = y + 3
    yl = y + sh - 3
    xs = x0 + idle_pre * cw
    half = cw / 2

    d = [f"M {x0},{yl}", f"L {xs},{yl}"]
    for i in range(n_active):
        cx = xs + i * cw
        d.extend([
            f"L {cx},{yh}",
            f"L {cx + half},{yh}",
            f"L {cx + half},{yl}",
            f"L {cx + cw},{yl}",
        ])
    d.append(f"L {xs + n_active * cw + idle_post * cw},{yl}")
    parts.append(
        f'<path d="{" ".join(d)}" fill="none" '
        f'stroke="{_CLK_COLOR}" stroke-width="1.5"/>'
    )


def _add_cs(
    parts: list[str],
    n_active: int,
    idle_pre: int,
    idle_post: int,
    x0: float,
    y: float,
    cw: int,
    sh: int,
):
    """Add CS# active-low SVG path."""
    yh = y + 3
    yl = y + sh - 3
    xs = x0 + idle_pre * cw
    xe = xs + n_active * cw
    xf = xe + idle_post * cw

    d = (
        f"M {x0},{yh} L {xs},{yh} L {xs},{yl} "
        f"L {xe},{yl} L {xe},{yh} L {xf},{yh}"
    )
    parts.append(
        f'<path d="{d}" fill="none" '
        f'stroke="{_CS_COLOR}" stroke-width="1.5"/>'
    )


def _add_digital(
    parts: list[str],
    bits: list[int],
    tri_pre: int,
    tri_post: int,
    x0: float,
    y: float,
    cw: int,
    sh: int,
    color: str,
):
    """Add a 1-bit digital signal with tristate periods (SPI mode)."""
    yh = y + 4
    yl = y + sh - 4
    ym = y + sh / 2

    # Tristate before
    if tri_pre > 0:
        xe = x0 + tri_pre * cw
        parts.append(
            f'<line x1="{x0}" y1="{ym}" x2="{xe}" y2="{ym}" '
            f'stroke="{color}" stroke-width="1" '
            f'stroke-dasharray="4,3" opacity="0.3"/>'
        )

    # Active bit-level waveform
    if bits:
        xs = x0 + tri_pre * cw
        d: list[str] = []
        for i, b in enumerate(bits):
            bx = xs + i * cw
            cy = yh if b else yl
            if i == 0:
                d.append(f"M {bx},{ym}")
                d.append(f"L {bx},{cy}")
            else:
                py = yh if bits[i - 1] else yl
                if cy != py:
                    d.append(f"L {bx},{cy}")
            d.append(f"L {bx + cw},{cy}")

        # Return to mid-level
        d.append(f"L {xs + len(bits) * cw},{ym}")

        parts.append(
            f'<path d="{" ".join(d)}" fill="none" '
            f'stroke="{color}" stroke-width="1.5"/>'
        )

        # Bit annotations (subtle)
        for i, b in enumerate(bits):
            bx = xs + i * cw + cw / 2
            parts.append(
                f'<text x="{bx}" y="{ym + 3}" text-anchor="middle" '
                f'fill="{color}" font-size="7" opacity="0.4">{b}</text>'
            )

    # Tristate after
    if tri_post > 0:
        x_start = x0 + (tri_pre + len(bits)) * cw
        x_end = x_start + tri_post * cw
        parts.append(
            f'<line x1="{x_start}" y1="{ym}" x2="{x_end}" y2="{ym}" '
            f'stroke="{color}" stroke-width="1" '
            f'stroke-dasharray="4,3" opacity="0.3"/>'
        )


def _add_bus(
    parts: list[str],
    vals: list[int],
    tri_pre: int,
    tri_post: int,
    x0: float,
    y: float,
    cw: int,
    sh: int,
    color: str,
):
    """Add a multi-bit bus signal with hex-annotated hexagonal slots
    (QSPI / Octal modes)."""
    yt = y + 5
    yb = y + sh - 5
    ym = y + sh / 2
    tw = min(5, cw * 0.18)  # transition-zone width at slot edges

    # Tristate before
    if tri_pre > 0:
        xe = x0 + tri_pre * cw
        parts.append(
            f'<line x1="{x0}" y1="{ym}" x2="{xe}" y2="{ym}" '
            f'stroke="{color}" stroke-width="1" '
            f'stroke-dasharray="4,3" opacity="0.3"/>'
        )

    # Bus hexagonal slots
    if vals:
        xs = x0 + tri_pre * cw
        for i, v in enumerate(vals):
            bx = xs + i * cw
            # Hexagonal / diamond bus shape
            d = (
                f"M {bx},{ym} "
                f"L {bx + tw},{yt} L {bx + cw - tw},{yt} "
                f"L {bx + cw},{ym} "
                f"L {bx + cw - tw},{yb} L {bx + tw},{yb} Z"
            )
            parts.append(
                f'<path d="{d}" fill="{color}" fill-opacity="0.07" '
                f'stroke="{color}" stroke-width="1.2"/>'
            )
            # Hex value label
            lbl = f"{v:X}" if v <= 0xF else f"{v:02X}"
            parts.append(
                f'<text x="{bx + cw / 2}" y="{ym + 4}" '
                f'text-anchor="middle" fill="{color}" '
                f'font-size="9" font-weight="500">{lbl}</text>'
            )

    # Tristate after
    if tri_post > 0:
        x_start = x0 + (tri_pre + len(vals)) * cw
        x_end = x_start + tri_post * cw
        parts.append(
            f'<line x1="{x_start}" y1="{ym}" x2="{x_end}" y2="{ym}" '
            f'stroke="{color}" stroke-width="1" '
            f'stroke-dasharray="4,3" opacity="0.3"/>'
        )
