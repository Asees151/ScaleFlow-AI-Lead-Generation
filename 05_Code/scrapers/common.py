"""
Shared helpers for the scrapers: logging, polite delays, domain cleanup,
and checkpoint / CSV saving.

Nothing here is site-specific. Both crunchbase_scraper.py and clutch_scraper.py
import from this module.
"""

import logging
import random
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import tldextract

# Repo root on sys.path so "from config import settings" works when this module
# is imported from anywhere.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import settings  # noqa: E402

# Hermetic domain extractor: use the snapshot bundled with tldextract, never hit
# the network mid-scrape (avoids a surprise hang while parsing pages).
_EXTRACT = tldextract.TLDExtract(suffix_list_urls=())


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
def get_logger(script_name: str) -> logging.Logger:
    """Return a logger that writes to both console and logs/<script>_<ts>.log."""
    settings.LOGS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    logfile = settings.LOGS_DIR / f"{script_name}_{ts}.log"

    logger = logging.getLogger(script_name)
    logger.setLevel(logging.INFO)
    logger.handlers.clear()  # avoid duplicate handlers on re-import
    logger.propagate = False

    fmt = logging.Formatter("%(asctime)s  %(levelname)-7s %(message)s", "%H:%M:%S")

    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    fh = logging.FileHandler(logfile, encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    logger.info("Logging to %s", logfile)
    return logger


# ---------------------------------------------------------------------------
# Politeness
# ---------------------------------------------------------------------------
def random_delay(min_s: float = None, max_s: float = None, logger: logging.Logger = None) -> None:
    """Sleep a random amount between min_s and max_s (defaults from settings)."""
    lo = settings.DELAY_MIN_SECONDS if min_s is None else min_s
    hi = settings.DELAY_MAX_SECONDS if max_s is None else max_s
    if hi < lo:
        hi = lo
    secs = random.uniform(lo, hi)
    if logger:
        logger.info("  ...delay %.1fs", secs)
    time.sleep(secs)


# ---------------------------------------------------------------------------
# Domain cleanup
# ---------------------------------------------------------------------------
def clean_domain(url: str) -> str:
    """
    Reduce a URL/website string to its root domain, lowercased.
    'https://www.Acme.com/about' -> 'acme.com'. Returns '' if not parseable.
    """
    if not url or not isinstance(url, str):
        return ""
    url = url.strip()
    if not url:
        return ""
    ext = _EXTRACT(url)
    if not ext.domain or not ext.suffix:
        return ""
    return f"{ext.domain}.{ext.suffix}".lower()


# ---------------------------------------------------------------------------
# CSV / checkpoint saving
# ---------------------------------------------------------------------------
def save_rows_csv(rows: list, path: Path, columns: list = None) -> int:
    """Write a list of dicts to CSV. If columns given, enforce that exact order."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows)
    if columns:
        for col in columns:
            if col not in df.columns:
                df[col] = ""
        df = df[columns]
    # utf-8-sig so Excel opens accented characters cleanly.
    df.to_csv(path, index=False, encoding="utf-8-sig")
    return len(df)


def save_checkpoint(rows: list, source: str, columns: list = None) -> Path:
    """Save a partial checkpoint into data/checkpoints/<source>_checkpoint.csv."""
    path = settings.CHECKPOINT_DIR / f"{source}_checkpoint.csv"
    save_rows_csv(rows, path, columns)
    return path


def now_iso() -> str:
    """ISO-8601 timestamp, second precision, for the scraped_at column."""
    return datetime.now().replace(microsecond=0).isoformat()
