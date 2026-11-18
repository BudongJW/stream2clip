"""Color parsing helpers and the default annotation palette."""

from __future__ import annotations

__all__ = ["RGBA", "PALETTE", "DEFAULT_COLOR", "parse_color", "to_hex"]

RGBA = tuple[int, int, int, int]

#: Default swatches shown in the editor toolbar (left to right).
PALETTE: dict[str, str] = {
    "red": "#EF4444",
    "pink": "#F472B6",
    "yellow": "#FACC15",
    "green": "#4ADE80",
    "blue": "#60A5FA",
    "purple": "#8B5CF6",
    "black": "#111111",
    "white": "#FFFFFF",
}

DEFAULT_COLOR = PALETTE["red"]


def parse_color(value: "str | tuple[int, ...] | list[int]") -> RGBA:
    """Parse ``#RGB``, ``#RRGGBB``, ``#RRGGBBAA``, ``0xRRGGBB``, palette names or tuples."""
    if isinstance(value, (tuple, list)):
        if len(value) == 3:
            r, g, b = value
            return (int(r), int(g), int(b), 255)
        if len(value) == 4:
            r, g, b, a = value
            return (int(r), int(g), int(b), int(a))
        raise ValueError(f"Color tuple must have 3 or 4 components, got {value!r}")

    text = value.strip()
    if text.lower() in PALETTE:
        text = PALETTE[text.lower()]
    if text.lower().startswith("0x"):
        text = "#" + text[2:]
    if not text.startswith("#"):
        raise ValueError(f"Unsupported color {value!r}")
    digits = text[1:]
    if len(digits) in (3, 4):
        digits = "".join(ch * 2 for ch in digits)
    if len(digits) == 6:
        digits += "FF"
    if len(digits) != 8:
        raise ValueError(f"Unsupported color {value!r}")
    try:
        r, g, b, a = (int(digits[i : i + 2], 16) for i in range(0, 8, 2))
    except ValueError as exc:  # pragma: no cover - defensive
        raise ValueError(f"Unsupported color {value!r}") from exc
    return (r, g, b, a)


def to_hex(color: "str | RGBA | tuple[int, int, int]", *, alpha: bool = False) -> str:
    r, g, b, a = parse_color(color)
    if alpha:
        return f"#{r:02X}{g:02X}{b:02X}{a:02X}"
    return f"#{r:02X}{g:02X}{b:02X}"
