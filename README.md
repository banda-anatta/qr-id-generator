# QR ID Card Generator

A Python script that reads member data from a CSV file and produces printable
ID cards, each containing member details and an embedded QR code.

---

## Features

- Generates a standalone QR code PNG per member
- Composites a full ID card (name, ID, status, validity date + QR)
- Graceful font fall-back (no crash when Arial is absent)
- Row-level validation with clear log messages
- All paths configurable via environment variables — no hard-coded user directories
- Exits with a meaningful status code (useful in CI/CD pipelines)

---

## Preview

```
┌──────────────────────────────────────────────┐
│  Name:        Jane Doe           ┌──────────┐ │
│  ID:          M-00123            │  ██ ██   │ │
│  Status:      Active             │  QR code │ │
│  Valid Until: 2025-12-31         │  ██ ██   │ │
│                                  └──────────┘ │
└──────────────────────────────────────────────┘
```

---

## Requirements

| Package          | Purpose              |
|------------------|----------------------|
| `Pillow`         | Image compositing    |
| `qrcode[pil]`    | QR code generation   |

Python **3.10+** is required (uses built-in `tuple[...]` type hints).

---

## Installation

```bash
# 1. Clone the repository
git clone https://github.com/<your-username>/qr-id-generator.git
cd qr-id-generator

# 2. Create and activate a virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate        # macOS / Linux
.venv\Scripts\activate           # Windows

# 3. Install dependencies
pip install -r requirements.txt
```

---

## CSV format

Create a file called `members.csv` (or point to your own — see Configuration):

```csv
Name,ID_Number,Status
Jane Doe,M-00123,Active
John Smith,M-00124,Inactive
Alice Johnson,M-00125,Pending
```

Column names are **case-sensitive**.  
Rows with missing or empty values are skipped with a warning.

---

## Configuration

All settings can be overridden via environment variables — no source code
edits required.

| Variable         | Default (relative to script) | Description                        |
|------------------|------------------------------|------------------------------------|
| `QR_CSV_PATH`    | `./members.csv`              | Path to the input CSV              |
| `QR_CODE_DIR`    | `./qr_codes`                 | Output directory for QR PNGs       |
| `ID_CARD_DIR`    | `./id_cards`                 | Output directory for ID card PNGs  |
| `QR_VALID_UNTIL` | `2025-12-31`                 | Expiry date printed on cards       |
| `QR_FONT_PATH`   | `arial.ttf`                  | Path to a TrueType font file       |

**Example — Linux / macOS:**
```bash
export QR_CSV_PATH=/data/club_members.csv
export QR_VALID_UNTIL=2026-12-31
python qr_id_generator.py
```

**Example — Windows (PowerShell):**
```powershell
$env:QR_CSV_PATH = "C:\data\club_members.csv"
$env:QR_VALID_UNTIL = "2026-12-31"
python qr_id_generator.py
```

---

## Usage

```bash
python qr_id_generator.py
```

Output is written to `./qr_codes/` and `./id_cards/` by default:

```
qr_codes/
  M-00123_qr.png
  M-00124_qr.png
id_cards/
  M-00123_id.png
  M-00124_id.png
```

### Exit codes

| Code | Meaning                                    |
|------|--------------------------------------------|
| `0`  | All rows processed successfully            |
| `1`  | Fatal error (e.g. CSV file not found)      |
| `2`  | Partial success — one or more rows skipped |

---

## Font notes

The script tries to load `arial.ttf` (configurable via `QR_FONT_PATH`).  

- **Windows**: Arial is usually available system-wide.  
- **macOS / Linux**: Supply a TTF path, or install `fonts-liberation`:
  ```bash
  sudo apt install fonts-liberation          # Debian / Ubuntu
  export QR_FONT_PATH=/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf
  ```
- **No font available**: The script falls back to PIL's built-in bitmap font.
  Cards will still be generated but text size and spacing will look different.

---

## Project structure

```
qr-id-generator/
├── qr_id_generator.py   # Main script
├── members.csv          # Sample input (add your own data)
├── requirements.txt     # Python dependencies
├── .gitignore
└── README.md
```

---

## .gitignore

A sensible `.gitignore` for this project:

```
# Virtual environment
.venv/
venv/

# Generated output – these can be large; exclude from version control
qr_codes/
id_cards/

# Real member data – never commit PII
members.csv

# Python bytecode
__pycache__/
*.pyc
*.pyo

# OS artefacts
.DS_Store
Thumbs.db
```

---

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-improvement`)
3. Commit your changes (`git commit -m "Add: my improvement"`)
4. Push to the branch (`git push origin feature/my-improvement`)
5. Open a Pull Request

---

## License

MIT — see [LICENSE](LICENSE) for details.
