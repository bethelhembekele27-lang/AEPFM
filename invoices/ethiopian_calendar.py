"""
Ethiopian -> Gregorian date conversion.

The Ethiopian calendar has 13 months (12 of 30 days plus a 5- or 6-day
Pagume). Meskerem 1 (Ethiopian New Year) falls on Sept 11 Gregorian, or
Sept 12 when the Ethiopian year runs into a Gregorian leap year.

This is the standard arithmetic for this calendar, not an approximation.
It was cross-checked against a JDN-based reference implementation for
Ethiopian New Year across 2013-2019 EC (including the leap-year case
1 Meskerem 2016 EC = 12 Sept 2023) and matched on every anchor.

IMPORTANT CAVEAT — this is a heuristic, not a determination. A printed
date like "23/01/2026" is ambiguous: it could be 23 Jan 2026 Gregorian, or
1 Tikimt 2026 Ethiopian (= 3 Oct 2033 Gregorian). Receipts in Ethiopia use
both calendars, and nothing on the image reliably distinguishes them. The
only reliable signal is that a receipt is a historical document, so a
conversion landing far in the future is almost certainly a misread of a
Gregorian date. `_is_plausible` uses that to decline converting rather
than store a confidently wrong date. When in doubt we return None and the
UI shows only the raw text as printed.
"""
import re
from datetime import date, timedelta


def is_gregorian_leap(year):
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def ethiopian_to_gregorian(eth_year, eth_month, eth_day):
    """
    eth_month: 1-13 (13 = Pagume). Returns a datetime.date.
    Raises ValueError if the month/day are out of range for the calendar.
    """
    if not (1 <= eth_month <= 13):
        raise ValueError(f"Invalid Ethiopian month: {eth_month}")
    if eth_month == 13 and eth_day > 6:
        raise ValueError(f"Invalid Pagume day: {eth_day}")
    if eth_month < 13 and eth_day > 30:
        raise ValueError(f"Invalid Ethiopian day: {eth_day}")

    new_year_greg_year = eth_year + 7
    new_year_offset_day = 12 if is_gregorian_leap(new_year_greg_year + 1) else 11
    new_year = date(new_year_greg_year, 9, new_year_offset_day)

    day_of_eth_year = (eth_month - 1) * 30 + (eth_day - 1)
    return new_year + timedelta(days=day_of_eth_year)


def _is_plausible(gregorian_date):
    """
    Reject conversions that land too far in the future. A receipt documents
    a payment that already happened, so anything more than a year ahead
    means we misread a Gregorian date as Ethiopian.
    """
    return gregorian_date <= date.today() + timedelta(days=365)


def parse_and_convert(raw_text):
    """
    Best-effort conversion of a printed date like '16/12/18' or '16/12/2018'
    (dd/mm/yy or dd/mm/yyyy), read as Ethiopian. Returns an ISO date string,
    or None if it doesn't parse or the result isn't plausible.

    Never raises: this is advisory-only, same principle as the extraction
    itself. A bad parse means no converted date is shown, not an error.
    """
    if not raw_text:
        return None
    match = re.match(r'^(\d{1,2})[/\-](\d{1,2})[/\-](\d{2,4})$', raw_text.strip())
    if not match:
        return None

    day, month, year = int(match.group(1)), int(match.group(2)), int(match.group(3))
    if year < 100:
        year += 2000  # short-year receipts are effectively always 20xx
    try:
        converted = ethiopian_to_gregorian(year, month, day)
    except (ValueError, OverflowError):
        return None

    if not _is_plausible(converted):
        return None
    return converted.isoformat()
