"""
qr_id_generator.py
==================
Generates QR-code-enhanced ID cards for Kannada Koota Luxembourg (KKL).

Reads directly from the KKL membership Excel file (.xlsx).

Excel columns used:
    'Category'                    – Family or Individual
    'Full name of the main member'– Primary member name
    'family member count'         – Number of members
    'Member ID'                   – Contains 'KKL2026-' prefix
    'Valid Until'                 – Expiry date (datetime in Excel)

At runtime the user is prompted for:
    - Starting sequential number (appended to KKL2026- prefix)
    - Validity date override (optional – Excel value used if Enter pressed)

Card design:
    - Yellow-to-red vertical gradient background
    - Member details in bold black text at the top
    - Large QR code centred below the text
    - KKL logo embedded in the centre of the QR code

Output written to:
    <QR_CODE_DIR>/<ID_Number>_qr.png   – standalone QR code with logo
    <ID_CARD_DIR>/<ID_Number>_id.png   – finished ID card

Dependencies:
    pip install qrcode[pil] Pillow openpyxl
"""

import logging
import os
import sys
from datetime import date, datetime
from pathlib import Path

import qrcode
import openpyxl
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
# Configuration
# ---------------------------------------------------------------------------
_SCRIPT_DIR = Path(__file__).resolve().parent

# Input Excel file
EXCEL_PATH: Path = Path(os.getenv("QR_EXCEL_PATH", _SCRIPT_DIR / "members.xlsx"))

# Output directories
QR_CODE_DIR: Path = Path(os.getenv("QR_CODE_DIR", _SCRIPT_DIR / "qr_codes"))
ID_CARD_DIR: Path = Path(os.getenv("ID_CARD_DIR", _SCRIPT_DIR / "id_cards"))

# KKL logo – place logo.png in the same folder as this script
LOGO_PATH: Path = Path(os.getenv("QR_LOGO_PATH", _SCRIPT_DIR / "logo.png"))

# Membership ID prefix
MEMBERSHIP_PREFIX: str = "KKL2026-"

# Card dimensions (pixels) – portrait orientation
CARD_WIDTH:  int = 550
CARD_HEIGHT: int = 750

# Default validity date fallback if not in Excel
VALID_UNTIL_DEFAULT: str = "2026-12-31"

# Font – DejaVu Bold for Codespaces; Arial on Windows
FONT_PATH: str = os.getenv(
    "QR_FONT_PATH",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
)

# QR code rendered size (pixels, square)
QR_RENDER_SIZE: int = 460

# Logo size as fraction of QR – keep <= 0.30 for reliable scanning
LOGO_FRACTION: float = 0.28

# Gradient colours (top → bottom)
GRADIENT_TOP:    tuple = (255, 213,   0)   # bright yellow
GRADIENT_BOTTOM: tuple = (180,  20,   0)   # deep red

# Text colour
COLOUR_TEXT: str = "black"

# Padding around text block (pixels)
TEXT_PADDING: int = 20

# ---------------------------------------------------------------------------
# Excel column names (must match exactly)
# ---------------------------------------------------------------------------
COL_CATEGORY:    str = "Category"
COL_NAME:        str = "Full name of the main member"
COL_COUNT:       str = "family member count"
COL_MEMBER_ID:   str = "Member ID"
COL_VALID_UNTIL: str = "Valid Until"

# ---------------------------------------------------------------------------
# Gradient background
# ---------------------------------------------------------------------------

def _make_gradient(width: int, height: int,
                   top: tuple, bottom: tuple) -> Image.Image:
    """
    Create a vertical linear gradient image from top colour to bottom colour.

    Args:
        width, height: Canvas size in pixels.
        top:           RGB colour at the top.
        bottom:        RGB colour at the bottom.

    Returns:
        RGB PIL Image filled with the gradient.
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
    Load fonts at three sizes: 28 / 24 / 20 pt.
    Falls back to PIL built-in bitmap font if TTF not found.

    Returns:
        Tuple of (font_large, font_medium, font_small).
    """
    try:
        font_large  = ImageFont.truetype(path, 28)
        font_medium = ImageFont.truetype(path, 24)
        font_small  = ImageFont.truetype(path, 20)
        logger.debug("Loaded font: %s", path)
    except (OSError, IOError):
        logger.warning("Font not found at '%s'. Using PIL default font.", path)
        default = ImageFont.load_default()
        font_large = font_medium = font_small = default
    return font_large, font_medium, font_small


# ---------------------------------------------------------------------------
# QR code with logo overlay
# ---------------------------------------------------------------------------

def generate_qr_code(data: str, id_number: str, output_dir: Path) -> Path:
    """
    Generate a QR code PNG with the KKL logo overlaid in its centre.

    Uses ERROR_CORRECT_H (~30% recovery) to allow the logo to cover
    the centre without breaking scannability.

    Args:
        data:       Payload string to encode.
        id_number:  Used as part of the output filename.
        output_dir: Directory where the PNG is saved.

    Returns:
        Path to the saved QR code PNG.
    """
    qr = qrcode.QRCode(
        version=1,
        box_size=10,
        border=4,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
    )
    qr.add_data(data)
    qr.make(fit=True)

    qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGBA")
    qr_img = qr_img.resize((QR_RENDER_SIZE, QR_RENDER_SIZE), Image.LANCZOS)

    # -- Overlay logo in centre -----------------------------------------------
    if LOGO_PATH.exists():
        logo_size = int(QR_RENDER_SIZE * LOGO_FRACTION)
        with Image.open(LOGO_PATH).convert("RGBA") as logo_raw:
            logo = logo_raw.resize((logo_size, logo_size), Image.LANCZOS)

        logo_x = (QR_RENDER_SIZE - logo_size) // 2
        logo_y = (QR_RENDER_SIZE - logo_size) // 2

        # White circular background behind logo
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
    else:
        logger.warning("Logo not found at '%s'. QR generated without logo.", LOGO_PATH)

    qr_final = qr_img.convert("RGB")
    qr_path  = output_dir / f"{id_number}_qr.png"
    qr_final.save(qr_path)
    return qr_path


# ---------------------------------------------------------------------------
# ID card creation
# ---------------------------------------------------------------------------

def create_id_card(
    name: str,
    id_number: str,
    category: str,
    valid_until: str,
    qr_dir: Path,
    card_dir: Path,
) -> Path:
    """
    Composite the KKL-style ID card:
        1. Yellow-to-red gradient background
        2. Bold member details text block at the top
        3. Large QR code (with embedded logo) centred below

    Args:
        name:        Full display name of the member.
        id_number:   Membership ID string (e.g. KKL2026-001).
        category:    'Individual' or 'Family'.
        valid_until: Expiry date in YYYY-MM-DD format.
        qr_dir:      Directory for the intermediate QR PNG.
        card_dir:    Directory for the finished ID card PNG.

    Returns:
        Path to the saved ID card PNG.
    """
    # -- Gradient background --------------------------------------------------
    card = _make_gradient(CARD_WIDTH, CARD_HEIGHT, GRADIENT_TOP, GRADIENT_BOTTOM)
    draw = ImageDraw.Draw(card)

    # -- Fonts ----------------------------------------------------------------
    font_large, font_medium, font_small = _load_fonts(FONT_PATH)

    # -- Format date as DD/MM/YYYY for display --------------------------------
    try:
        d = date.fromisoformat(valid_until)
        validity_display = d.strftime("%d/%m/%Y")
    except ValueError:
        validity_display = valid_until

    # -- Text block -----------------------------------------------------------
    lines = [
        (f"Member:          {name}",             font_large),
        (f"Membership ID: {id_number}",           font_large),
        (f"Category:        {category}",          font_medium),
        (f"Validity:          {validity_display}", font_medium),
    ]

    y = TEXT_PADDING + 10
    for text, font in lines:
        draw.text((TEXT_PADDING, y), text, fill=COLOUR_TEXT, font=font)
        bbox = draw.textbbox((0, 0), text, font=font)
        y += (bbox[3] - bbox[1]) + 14

    # -- QR code --------------------------------------------------------------
    qr_payload = (
        f"Member:{name}\n"
        f"ID:{id_number}\n"
        f"Category:{category}\n"
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
# Excel processing
# ---------------------------------------------------------------------------

def process_excel(
    excel_path: Path,
    qr_dir: Path,
    card_dir: Path,
    start_sequence: int,
    valid_until_override: str | None,
) -> tuple[int, int]:
    """
    Read the KKL membership Excel file and generate one ID card per valid row.

    Membership ID is built as: KKL2026- + zero-padded sequence number.
    Category is taken directly from the Excel 'Category' column.
    Valid Until comes from the Excel unless the user provided an override.

    Args:
        excel_path:           Path to the .xlsx file.
        qr_dir:               Destination for QR code PNGs.
        card_dir:             Destination for ID card PNGs.
        start_sequence:       First sequential number for Membership IDs.
        valid_until_override: If provided, overrides the Excel date for all cards.

    Returns:
        Tuple of (success_count, skip_count).
    """
    wb = openpyxl.load_workbook(excel_path)
    ws = wb.active

    # Read header row to map column names to indices
    headers = [cell.value for cell in next(ws.iter_rows(min_row=1, max_row=1))]
    logger.info("Excel columns found: %s", headers)

    # Verify required columns exist
    required_cols = [COL_CATEGORY, COL_NAME, COL_VALID_UNTIL]
    for col in required_cols:
        if col not in headers:
            logger.error("Required column '%s' not found in Excel. Aborting.", col)
            sys.exit(1)

    # Build column index map
    col_idx = {name: idx for idx, name in enumerate(headers)}

    success = 0
    skipped = 0
    seq     = start_sequence

    # Process data rows (skip header row 1)
    for row_number, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):

        # -- Extract values ---------------------------------------------------
        name     = row[col_idx[COL_NAME]]
        category = row[col_idx[COL_CATEGORY]]
        val_raw  = row[col_idx[COL_VALID_UNTIL]]

        # -- Skip empty rows --------------------------------------------------
        if not name or not str(name).strip():
            logger.warning("Row %d: empty name – skipping.", row_number)
            skipped += 1
            continue

        if not category or not str(category).strip():
            logger.warning("Row %d: empty category – skipping.", row_number)
            skipped += 1
            continue

        name     = str(name).strip()
        category = str(category).strip()

        # -- Resolve Valid Until ----------------------------------------------
        if valid_until_override:
            # User provided an override at startup – use for all cards
            valid_until = valid_until_override
        elif isinstance(val_raw, datetime):
            # Excel stores dates as datetime objects
            valid_until = val_raw.strftime("%Y-%m-%d")
        elif isinstance(val_raw, str) and val_raw.strip():
            valid_until = val_raw.strip()
        else:
            # Fall back to default
            valid_until = VALID_UNTIL_DEFAULT
            logger.warning("Row %d: no valid date found, using default %s.",
                           row_number, VALID_UNTIL_DEFAULT)

        # -- Build Membership ID ----------------------------------------------
        id_number = f"{MEMBERSHIP_PREFIX}{seq:03d}"

        # -- Generate card ----------------------------------------------------
        try:
            create_id_card(
                name=name,
                id_number=id_number,
                category=category,
                valid_until=valid_until,
                qr_dir=qr_dir,
                card_dir=card_dir,
            )
            success += 1
            seq += 1    # advance only on success

        except Exception:
            logger.exception("Row %d: unexpected error for '%s'.", row_number, name)
            skipped += 1

    return success, skipped


# ---------------------------------------------------------------------------
# Interactive prompts
# ---------------------------------------------------------------------------

def _prompt_start_sequence() -> int:
    """
    Ask the user for the starting sequential number for Membership IDs.

    Example: entering 1 → KKL2026-001, KKL2026-002, ...
    Pressing Enter defaults to 1.

    Returns:
        Starting sequence number as a positive integer.
    """
    while True:
        raw = input(f"\nEnter starting sequence number for {MEMBERSHIP_PREFIX} [1]: ").strip()
        if not raw:
            print("Using default: 1")
            return 1
        try:
            n = int(raw)
            if n < 1:
                raise ValueError
            return n
        except ValueError:
            print("  x Please enter a positive whole number (e.g. 1, 13, 100).")


def _prompt_valid_until_override() -> str | None:
    """
    Optionally ask the user to override the Valid Until date for all cards.

    Pressing Enter without input keeps the date from the Excel file.

    Returns:
        Date string in YYYY-MM-DD format, or None to use Excel dates.
    """
    print(f"\nValid Until date is read from the Excel file (currently 2026-12-31).")
    raw = input("Press Enter to use Excel dates, or type a date to override all [YYYY-MM-DD]: ").strip()

    if not raw:
        print("Using dates from Excel file.")
        return None

    while True:
        try:
            date.fromisoformat(raw)
            return raw
        except ValueError:
            raw = input("  x Invalid format. Enter YYYY-MM-DD or press Enter to use Excel dates: ").strip()
            if not raw:
                return None


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """
    1. Prompt for starting sequence number and optional date override
    2. Validate paths and create output directories
    3. Process Excel file and generate all ID cards
    """
    print("\n=== KKL ID Card Generator ===")

    # -- Prompts --------------------------------------------------------------
    start_sequence       = _prompt_start_sequence()
    valid_until_override = _prompt_valid_until_override()

    logger.info("Starting ID      : %s%03d", MEMBERSHIP_PREFIX, start_sequence)
    logger.info("Valid Until      : %s",
                valid_until_override if valid_until_override else "from Excel")

    # -- Logo check -----------------------------------------------------------
    if not LOGO_PATH.exists():
        logger.warning(
            "Logo not found at '%s'. Place logo.png next to this script.", LOGO_PATH
        )

    # -- Excel check ----------------------------------------------------------
    if not EXCEL_PATH.exists():
        logger.error("Excel file not found: %s", EXCEL_PATH)
        sys.exit(1)

    # -- Output directories ---------------------------------------------------
    QR_CODE_DIR.mkdir(parents=True, exist_ok=True)
    ID_CARD_DIR.mkdir(parents=True, exist_ok=True)
    logger.info("QR codes  -> %s", QR_CODE_DIR)
    logger.info("ID cards  -> %s", ID_CARD_DIR)

    # -- Generate -------------------------------------------------------------
    logger.info("Reading from: %s", EXCEL_PATH)
    success, skipped = process_excel(
        EXCEL_PATH, QR_CODE_DIR, ID_CARD_DIR, start_sequence, valid_until_override
    )

    logger.info("Done. %d card(s) created, %d row(s) skipped.", success, skipped)
    if skipped:
        sys.exit(2)


if __name__ == "__main__":
    main()
