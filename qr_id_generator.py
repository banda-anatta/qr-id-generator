"""
qr_id_generator.py
==================
Generates QR-code-enhanced ID cards from a CSV data source.

Each row in the CSV must contain at least three columns:
    Name        – Full display name of the member
    ID_Number   – Unique identifier (used for filenames too)
    Status      – Membership / access status

Output artefacts written to disk:
    <QR_CODE_DIR>/<ID_Number>_qr.png   – standalone QR code image
    <ID_CARD_DIR>/<ID_Number>_id.png   – finished ID card with embedded QR code

Dependencies (install via requirements.txt):
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
# Logging – write INFO+ to stdout and WARNING+ to stderr
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# All path values fall back to sensible relative defaults so the script works
# out of the box after cloning, while still honouring environment overrides.
# ---------------------------------------------------------------------------

# Base directory of the script itself – used to build default relative paths
_SCRIPT_DIR = Path(__file__).resolve().parent

# Input CSV – columns required: Name, ID_Number, Status
CSV_PATH: Path = Path(os.getenv("QR_CSV_PATH", _SCRIPT_DIR / "members.csv"))

# Output directories
QR_CODE_DIR: Path = Path(os.getenv("QR_CODE_DIR", _SCRIPT_DIR / "qr_codes"))
ID_CARD_DIR: Path = Path(os.getenv("ID_CARD_DIR", _SCRIPT_DIR / "id_cards"))

# Card dimensions (pixels)
CARD_WIDTH: int = 600
CARD_HEIGHT: int = 350

# Validity date printed on every card (ISO format: YYYY-MM-DD)
VALID_UNTIL: str = os.getenv("QR_VALID_UNTIL", "2025-12-31")

# Font – falls back to PIL's built-in bitmap font when the TTF is missing
FONT_PATH: str = os.getenv("QR_FONT_PATH", "arial.ttf")

# QR code image size pasted onto the ID card (pixels, square)
QR_EMBED_SIZE: int = 150

# Colour palette
COLOUR_BACKGROUND: str = "white"
COLOUR_PRIMARY_TEXT: str = "black"
COLOUR_STATUS_TEXT: str = "blue"
COLOUR_BORDER: str = "#CCCCCC"

# Required CSV column names
CSV_COL_NAME: str = "Name"
CSV_COL_ID: str = "ID_Number"
CSV_COL_STATUS: str = "Status"

# ---------------------------------------------------------------------------
# Font helper
# ---------------------------------------------------------------------------

def _load_fonts(path: str) -> tuple[ImageFont.FreeTypeFont, ...]:
    """
    Load three TrueType fonts at sizes 30 / 24 / 20 pt.

    Falls back gracefully to PIL's built-in default bitmap font when the
    requested TTF file cannot be found.  The built-in font is the same object
    for all three 'sizes'; callers must accept this.

    Args:
        path: Filesystem path (or filename on PATH) of a .ttf file.

    Returns:
        Tuple of (font_large, font_medium, font_small).
    """
    try:
        font_large  = ImageFont.truetype(path, 30)
        font_medium = ImageFont.truetype(path, 24)
        font_small  = ImageFont.truetype(path, 20)
        logger.debug("Loaded TrueType font: %s", path)
    except (OSError, IOError):
        logger.warning(
            "TrueType font not found at '%s'. "
            "Falling back to PIL default font – text layout may differ.",
            path,
        )
        default = ImageFont.load_default()
        font_large = font_medium = font_small = default

    return font_large, font_medium, font_small


# ---------------------------------------------------------------------------
# QR code generation
# ---------------------------------------------------------------------------

def generate_qr_code(data: str, id_number: str, output_dir: Path) -> Path:
    """
    Encode *data* as a QR code and save it to *output_dir*.

    The QR code starts at version 1 and grows automatically (fit=True) to
    accommodate the payload, so callers do not need to worry about data length.

    Args:
        data:       String payload to encode (e.g. multi-line vCard snippet).
        id_number:  Member identifier used as part of the output filename.
        output_dir: Directory in which to save the PNG file.

    Returns:
        Path to the saved QR code PNG.

    Raises:
        OSError: If the file cannot be written.
    """
    qr = qrcode.QRCode(
        version=1,         # start small; auto-grows via fit=True below
        box_size=10,       # pixels per QR module (dot)
        border=4,          # quiet-zone modules around the code (spec min = 4)
        error_correction=qrcode.constants.ERROR_CORRECT_M,  # ~15 % recovery
    )
    qr.add_data(data)
    qr.make(fit=True)  # automatically increase version if data overflows

    img = qr.make_image(fill_color="black", back_color="white")

    qr_path = output_dir / f"{id_number}_qr.png"
    img.save(qr_path)
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
    Composite an ID card image that contains member details and an embedded
    QR code, then save it as a PNG.

    Layout (approximate, in pixels):
        y=20   Name  (large font, black)
        y=70   ID    (large font, black)
        y=120  Status (medium font, blue)
        y=160  Valid Until (small font, black)
        x=400,y=50  QR code (150×150 px)
        bottom border line

    Args:
        name:        Full display name.
        id_number:   Unique member identifier.
        status:      Membership / access level string.
        qr_dir:      Directory where the intermediate QR PNG is written.
        card_dir:    Directory where the finished ID card PNG is written.
        valid_until: Human-readable expiry date string on the card face.

    Returns:
        Path to the saved ID card PNG.

    Raises:
        OSError: If either the QR code or the card file cannot be written.
    """
    # -- Canvas ---------------------------------------------------------------
    card = Image.new("RGB", (CARD_WIDTH, CARD_HEIGHT), COLOUR_BACKGROUND)
    draw = ImageDraw.Draw(card)

    # -- Fonts ----------------------------------------------------------------
    font_large, font_medium, font_small = _load_fonts(FONT_PATH)

    # -- Text -----------------------------------------------------------------
    draw.text((20, 20),  f"Name:        {name}",              fill=COLOUR_PRIMARY_TEXT, font=font_large)
    draw.text((20, 70),  f"ID:            {id_number}",       fill=COLOUR_PRIMARY_TEXT, font=font_large)
    draw.text((20, 120), f"Status:      {status}",            fill=COLOUR_STATUS_TEXT,  font=font_medium)
    draw.text((20, 160), f"Valid Until: {valid_until}",       fill=COLOUR_PRIMARY_TEXT, font=font_small)

    # -- Decorative border at the bottom of the card -------------------------
    draw.line(
        [(0, CARD_HEIGHT - 10), (CARD_WIDTH, CARD_HEIGHT - 10)],
        fill=COLOUR_BORDER,
        width=4,
    )

    # -- Embed QR code -------------------------------------------------------
    # Build the QR payload – keep it concise; scanners have limited display area
    qr_payload = (
        f"Name:{name}\n"
        f"ID:{id_number}\n"
        f"Status:{status}\n"
        f"ValidUntil:{valid_until}"
    )
    qr_path = generate_qr_code(qr_payload, id_number, qr_dir)

    # Open, resize, then paste – using LANCZOS for high-quality downscaling
    with Image.open(qr_path) as qr_img:
        qr_resized = qr_img.resize((QR_EMBED_SIZE, QR_EMBED_SIZE), Image.LANCZOS)

    # Paste position: right side of card with a small margin
    qr_x = CARD_WIDTH - QR_EMBED_SIZE - 30
    qr_y = (CARD_HEIGHT - QR_EMBED_SIZE) // 2  # vertically centred
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
    Check that a CSV row contains all required columns and that no value is
    empty.

    Args:
        row:        DictReader row (column → value mapping).
        row_number: 1-based row index used in log messages.

    Returns:
        True if the row is valid; False otherwise.
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
) -> tuple[int, int]:
    """
    Read *csv_path* row by row and generate an ID card for each valid member.

    Args:
        csv_path: Path to the input CSV file.
        qr_dir:   Destination directory for QR code images.
        card_dir: Destination directory for finished ID cards.

    Returns:
        Tuple of (success_count, skip_count).

    Raises:
        FileNotFoundError: If *csv_path* does not exist.
        csv.Error:         On malformed CSV content.
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
                )
                success += 1
            except Exception:  # pragma: no cover – surface unexpected errors
                logger.exception(
                    "Row %d: unexpected error while processing member '%s' (ID=%s).",
                    row_number, name, id_number,
                )
                skipped += 1

    return success, skipped


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """
    Validate configuration, create output directories, then process the CSV.
    Exits with a non-zero status code on fatal errors.
    """
    # -- Validate input file -------------------------------------------------
    if not CSV_PATH.exists():
        logger.error("CSV file not found: %s", CSV_PATH)
        sys.exit(1)

    # -- Ensure output directories exist ------------------------------------
    QR_CODE_DIR.mkdir(parents=True, exist_ok=True)
    ID_CARD_DIR.mkdir(parents=True, exist_ok=True)
    logger.info("QR codes  → %s", QR_CODE_DIR)
    logger.info("ID cards  → %s", ID_CARD_DIR)

    # -- Process -------------------------------------------------------------
    logger.info("Starting ID card generation from: %s", CSV_PATH)
    success, skipped = process_csv(CSV_PATH, QR_CODE_DIR, ID_CARD_DIR)

    # -- Summary -------------------------------------------------------------
    logger.info(
        "Done. %d card(s) created, %d row(s) skipped.",
        success, skipped,
    )
    if skipped:
        sys.exit(2)   # partial success – useful for CI pipelines


if __name__ == "__main__":
    main()
