"""
qr_id_generator.py
==================
Generates QR-code-enhanced ID cards for Kannada Koota Luxembourg (KKL).

Card design matches the KKL sample:
    - Yellow-to-red vertical gradient background
    - Member details in bold black text at the top
    - Large QR code centred below the text
    - KKL logo embedded in the centre of the QR code
    - High error-correction (H) so the logo does not break scanning

CSV columns required:
    Name        – Full display name of the member
    ID_Number   – Unique membership identifier (e.g. KKL2025130322)
    Status      – Membership category (e.g. Family, Individual)

Output written to:
    <QR_CODE_DIR>/<ID_Number>_qr.png   – standalone QR code with logo
    <ID_CARD_DIR>/<ID_Number>_id.png   – finished ID card

Dependencies:
    pip install qrcode[pil] Pillow
"""

import csv
import logging
import os
import sys
from datetime import date
from pathlib import Path

import qrcode
from PIL import Image, ImageDraw, ImageFont

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration – all paths can be overridden via environment variables
# ---------------------------------------------------------------------------
_SCRIPT_DIR = Path(__file__).resolve().parent

# Input CSV
CSV_PATH: Path = Path(os.getenv("QR_CSV_PATH", _SCRIPT_DIR / "members.csv"))

# Output directories
QR_CODE_DIR: Path = Path(os.getenv("QR_CODE_DIR", _SCRIPT_DIR / "qr_codes"))
ID_CARD_DIR: Path = Path(os.getenv("ID_CARD_DIR", _SCRIPT_DIR / "id_cards"))

# KKL logo – placed in the centre of every QR code
# Place logo.png in the same folder as this script, or set the env variable
LOGO_PATH: Path = Path(os.getenv("QR_LOGO_PATH", _SCRIPT_DIR / "logo.png"))

# Card dimensions (pixels) – portrait orientation to match sample
CARD_WIDTH:  int = 550
CARD_HEIGHT: int = 750

# Default validity date (YYYY-MM-DD) – overridden by interactive prompt
VALID_UNTIL: str = os.getenv("QR_VALID_UNTIL", "2025-12-31")

# Font – DejaVu Bold works well in Codespaces; Arial on Windows
FONT_PATH: str = os.getenv(
    "QR_FONT_PATH",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
)

# QR code rendered size before pasting onto the card (pixels, square)
QR_RENDER_SIZE: int = 460

# Logo overlaid on the QR code – as a fraction of the QR size
# Keep <= 0.30 so scanners can still decode despite the obstruction
LOGO_FRACTION: float = 0.28

# Gradient colours (top -> bottom)
GRADIENT_TOP:    tuple = (255, 213,   0)   # bright yellow
GRADIENT_BOTTOM: tuple = (180,  20,   0)   # deep red

# Text colour
COLOUR_TEXT: str = "black"

# Padding around text block (pixels)
TEXT_PADDING: int = 20

# Required CSV column names
CSV_COL_NAME:   str = "Name"
CSV_COL_ID:     str = "ID_Number"
CSV_COL_STATUS: str = "Status"

# ---------------------------------------------------------------------------
# Gradient background helper
# ---------------------------------------------------------------------------

def _make_gradient(width: int, height: int,
                   top: tuple, bottom: tuple) -> Image.Image:
    """
    Create a vertical linear gradient image from *top* colour to *bottom* colour.

    Args:
        width:  Image width in pixels.
        height: Image height in pixels.
        top:    RGB tuple for the top of the gradient.
        bottom: RGB tuple for the bottom of the gradient.

    Returns:
        A new RGB PIL Image filled with the gradient.
    """
    base = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(base)

    for y in range(height):
        ratio = y / (height - 1)
        r = int(top[0] + (bottom[0] - top[0]) * ratio)
        g = int(top[1] + (bottom[1] - top[1]) * ratio)
        b = int(top[2] + (bottom[2] - top[2]) * ratio)
        draw.line([(0, y), (width, y)], fill=(r, g, b))

    return base


# ---------------------------------------------------------------------------
# Font helper
# ---------------------------------------------------------------------------

def _load_fonts(path: str) -> tuple:
    """
    Load bold fonts at three sizes: 28 / 24 / 20 pt.

    Falls back to PIL built-in bitmap font when the TTF cannot be found.

    Args:
        path: Filesystem path to a .ttf font file.

    Returns:
        Tuple of (font_large, font_medium, font_small).
    """
    try:
        font_large  = ImageFont.truetype(path, 28)
        font_medium = ImageFont.truetype(path, 24)
        font_small  = ImageFont.truetype(path, 20)
        logger.debug("Loaded font: %s", path)
    except (OSError, IOError):
        logger.warning(
            "Font not found at '%s'. Falling back to PIL default font.", path
        )
        default = ImageFont.load_default()
        font_large = font_medium = font_small = default

    return font_large, font_medium, font_small


# ---------------------------------------------------------------------------
# QR code with logo overlay
# ---------------------------------------------------------------------------

def generate_qr_code(data: str, id_number: str, output_dir: Path) -> Path:
    """
    Generate a QR code PNG with the KKL logo overlaid in its centre.

    Error correction is set to H (~30% recovery) so the logo can cover
    up to ~28% of the QR surface without breaking scannability.

    Args:
        data:       Payload string to encode.
        id_number:  Used as part of the output filename.
        output_dir: Directory where the PNG is saved.

    Returns:
        Path to the saved QR code PNG.
    """
    # -- Build QR code --------------------------------------------------------
    qr = qrcode.QRCode(
        version=1,
        box_size=10,
        border=4,
        error_correction=qrcode.constants.ERROR_CORRECT_H,  # allows logo overlay
    )
    qr.add_data(data)
    qr.make(fit=True)

    qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGBA")
    qr_img = qr_img.resize((QR_RENDER_SIZE, QR_RENDER_SIZE), Image.LANCZOS)

    # -- Overlay logo in the centre ------------------------------------------
    if LOGO_PATH.exists():
        logo_size = int(QR_RENDER_SIZE * LOGO_FRACTION)

        with Image.open(LOGO_PATH).convert("RGBA") as logo_raw:
            logo = logo_raw.resize((logo_size, logo_size), Image.LANCZOS)

        logo_x = (QR_RENDER_SIZE - logo_size) // 2
        logo_y = (QR_RENDER_SIZE - logo_size) // 2

        # White circular background behind logo for clean appearance
        mask_img  = Image.new("RGBA", (QR_RENDER_SIZE, QR_RENDER_SIZE), (0, 0, 0, 0))
        mask_draw = ImageDraw.Draw(mask_img)
        padding   = 6
        mask_draw.ellipse(
            [logo_x - padding, logo_y - padding,
             logo_x + logo_size + padding, logo_y + logo_size + padding],
            fill=(255, 255, 255, 255),
        )
        qr_img = Image.alpha_composite(qr_img, mask_img)
        qr_img.paste(logo, (logo_x, logo_y), mask=logo)
        logger.debug("Logo overlaid on QR code.")
    else:
        logger.warning(
            "Logo not found at '%s'. Generating QR without logo.", LOGO_PATH
        )

    qr_final = qr_img.convert("RGB")
    qr_path  = output_dir / f"{id_number}_qr.png"
    qr_final.save(qr_path)
    logger.debug("QR code saved: %s", qr_path)
    return qr_path


# ---------------------------------------------------------------------------
# ID card creation
# ---------------------------------------------------------------------------

def create_id_card(
    name: str,
    id_number: str,
    status: str,
    qr_dir: Path,
    card_dir: Path,
    valid_until: str = VALID_UNTIL,
) -> Path:
    """
    Composite the KKL-style ID card:
        1. Yellow-to-red gradient background
        2. Bold member details text block at the top
        3. Large QR code (with embedded logo) centred below

    Args:
        name:        Full display name of the member.
        id_number:   Unique membership ID string.
        status:      Membership category / status.
        qr_dir:      Directory for the intermediate QR PNG.
        card_dir:    Directory for the finished ID card PNG.
        valid_until: Expiry date string printed on the card.

    Returns:
        Path to the saved ID card PNG.
    """
    # -- Gradient background --------------------------------------------------
    card = _make_gradient(CARD_WIDTH, CARD_HEIGHT, GRADIENT_TOP, GRADIENT_BOTTOM)
    draw = ImageDraw.Draw(card)

    # -- Fonts ----------------------------------------------------------------
    font_large, font_medium, font_small = _load_fonts(FONT_PATH)

    # -- Format validity date as DD/MM/YYYY to match sample card --------------
    try:
        d = date.fromisoformat(valid_until)
        validity_display = d.strftime("%d/%m/%Y")
    except ValueError:
        validity_display = valid_until

    # -- Text block -----------------------------------------------------------
    lines = [
        (f"Member:  {name}",           font_large),
        (f"Membership ID: {id_number}", font_large),
        (f"Category: {status}",         font_medium),
        (f"Validity: {validity_display}", font_medium),
    ]

    y = TEXT_PADDING + 10
    for text, font in lines:
        draw.text((TEXT_PADDING, y), text, fill=COLOUR_TEXT, font=font)
        bbox = draw.textbbox((0, 0), text, font=font)
        y += (bbox[3] - bbox[1]) + 14   # line height + spacing

    # -- QR code (centred horizontally, below text) ---------------------------
    qr_payload = (
        f"Member:{name}\n"
        f"ID:{id_number}\n"
        f"Category:{status}\n"
        f"Validity:{validity_display}"
    )
    qr_path = generate_qr_code(qr_payload, id_number, qr_dir)

    with Image.open(qr_path) as qr_img:
        qr_resized = qr_img.resize((QR_RENDER_SIZE, QR_RENDER_SIZE), Image.LANCZOS)

    qr_x = (CARD_WIDTH  - QR_RENDER_SIZE) // 2
    qr_y = y + 20
    card.paste(qr_resized, (qr_x, qr_y))

    # -- Save -----------------------------------------------------------------
    output_path = card_dir / f"{id_number}_id.png"
    card.save(output_path)
    logger.info("Created ID card: %s", output_path)
    return output_path


# ---------------------------------------------------------------------------
# CSV processing
# ---------------------------------------------------------------------------

def _validate_row(row: dict, row_number: int) -> bool:
    """
    Verify a CSV row has all required non-empty columns.

    Args:
        row:        DictReader row.
        row_number: 1-based index for log messages.

    Returns:
        True if valid; False to skip.
    """
    required = (CSV_COL_NAME, CSV_COL_ID, CSV_COL_STATUS)
    for col in required:
        if col not in row:
            logger.error("Row %d: missing column '%s' – skipping.", row_number, col)
            return False
        if not str(row[col]).strip():
            logger.warning("Row %d: column '%s' is empty – skipping.", row_number, col)
            return False
    return True


def process_csv(
    csv_path: Path,
    qr_dir: Path,
    card_dir: Path,
    valid_until: str = VALID_UNTIL,
) -> tuple[int, int]:
    """
    Read the CSV and generate an ID card for each valid member row.

    Args:
        csv_path:    Path to the input CSV file.
        qr_dir:      Destination for QR code PNGs.
        card_dir:    Destination for ID card PNGs.
        valid_until: Expiry date applied to all cards in this run.

    Returns:
        Tuple of (success_count, skip_count).
    """
    success = 0
    skipped = 0

    with csv_path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row_number, row in enumerate(reader, start=1):
            if not _validate_row(row, row_number):
                skipped += 1
                continue

            name      = row[CSV_COL_NAME].strip()
            id_number = row[CSV_COL_ID].strip()
            status    = row[CSV_COL_STATUS].strip()

            try:
                create_id_card(
                    name=name,
                    id_number=id_number,
                    status=status,
                    qr_dir=qr_dir,
                    card_dir=card_dir,
                    valid_until=valid_until,
                )
                success += 1
            except Exception:
                logger.exception(
                    "Row %d: unexpected error for '%s' (ID=%s).",
                    row_number, name, id_number,
                )
                skipped += 1

    return success, skipped


# ---------------------------------------------------------------------------
# Interactive date prompt
# ---------------------------------------------------------------------------

def _prompt_valid_until() -> str:
    """
    Prompt the user to enter the card expiry date.

    Loops until a valid YYYY-MM-DD string is entered.
    Pressing Enter accepts the VALID_UNTIL default.

    Returns:
        Validated date string in YYYY-MM-DD format.
    """
    while True:
        raw = input(f"\nEnter Valid Until date [{VALID_UNTIL}]: ").strip()
        if not raw:
            print(f"Using default: {VALID_UNTIL}")
            return VALID_UNTIL
        try:
            date.fromisoformat(raw)
            return raw
        except ValueError:
            print("  x Invalid format. Please use YYYY-MM-DD (e.g. 2026-12-31).")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """
    1. Prompt for expiry date
    2. Validate paths and create output directories
    3. Process CSV and generate all ID cards
    """
    valid_until = _prompt_valid_until()
    logger.info("Valid Until date set to: %s", valid_until)

    if not LOGO_PATH.exists():
        logger.warning(
            "Logo not found at '%s'. Place logo.png next to this script to embed it.",
            LOGO_PATH,
        )

    if not CSV_PATH.exists():
        logger.error("CSV file not found: %s", CSV_PATH)
        sys.exit(1)

    QR_CODE_DIR.mkdir(parents=True, exist_ok=True)
    ID_CARD_DIR.mkdir(parents=True, exist_ok=True)
    logger.info("QR codes  -> %s", QR_CODE_DIR)
    logger.info("ID cards  -> %s", ID_CARD_DIR)

    logger.info("Starting ID card generation from: %s", CSV_PATH)
    success, skipped = process_csv(CSV_PATH, QR_CODE_DIR, ID_CARD_DIR, valid_until)

    logger.info("Done. %d card(s) created, %d row(s) skipped.", success, skipped)
    if skipped:
        sys.exit(2)


if __name__ == "__main__":
    main()
