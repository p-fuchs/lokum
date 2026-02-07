import re

from pydantic import BaseModel

_CURRENCY_MAP: dict[str, str] = {
    "zł": "PLN",
    "pln": "PLN",
    "eur": "EUR",
    "€": "EUR",
    "usd": "USD",
    "$": "USD",
}

_CURRENCY_PATTERN = re.compile(
    r"(?:" + "|".join(re.escape(k) for k in _CURRENCY_MAP) + r")",
    re.IGNORECASE,
)

_NUMBER_PATTERN = re.compile(r"(\d[\d\s,.]*\d|\d)")


class ParsedPrice(BaseModel):
    raw: str
    amount: float | None = None
    currency: str | None = None
    notes: str | None = None


def parse_price(raw: str) -> ParsedPrice:
    """Parse a raw price string into structured components."""
    text = raw.strip()
    remaining = text

    # Extract amount
    amount: float | None = None
    number_match = _NUMBER_PATTERN.search(remaining)
    if number_match:
        num_str = number_match.group(1)
        num_str = num_str.replace(" ", "").replace("\u00a0", "")
        # Handle comma as decimal separator (e.g. "3100,50")
        # vs comma as thousand separator (e.g. "3,100")
        if "," in num_str and "." in num_str:
            # Both present: comma is thousand sep, dot is decimal
            num_str = num_str.replace(",", "")
        elif "," in num_str:
            parts = num_str.split(",")
            if len(parts) == 2 and len(parts[1]) <= 2:
                # Comma as decimal separator
                num_str = num_str.replace(",", ".")
            else:
                # Comma as thousand separator
                num_str = num_str.replace(",", "")
        try:
            amount = float(num_str)
        except ValueError:
            pass
        remaining = remaining[: number_match.start()] + remaining[number_match.end() :]

    # Extract currency
    currency: str | None = None
    currency_match = _CURRENCY_PATTERN.search(remaining)
    if currency_match:
        currency = _CURRENCY_MAP[currency_match.group(0).lower()]
        remaining = (
            remaining[: currency_match.start()] + remaining[currency_match.end() :]
        )

    # Extract notes (whatever is left, cleaned up)
    notes_text = remaining.strip().strip("/\\-–—,;:.").strip()
    notes: str | None = notes_text if notes_text else None

    return ParsedPrice(
        raw=text,
        amount=amount,
        currency=currency,
        notes=notes,
    )
