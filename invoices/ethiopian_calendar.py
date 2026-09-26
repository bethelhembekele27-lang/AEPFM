"""
Ethiopian -> Gregorian date conversion.

The Ethiopian calendar has 13 months (12 of 30 days plus a 5- or 6-day
Pagume). Meskerem 1 (Ethiopian New Year) falls on Sept 11 Gregorian, or
Sept 12 when the Ethiopian year runs into a Gregorian leap year.

This is the standard arithmetic for this calendar, not an approximation.
It was cross-checked against a JDN-based reference implementation for
Ethiopian New Year across 2013-2019 EC (including the leap-year case
1 Meskerem 2016 EC = 12 Sept 2023) and matched on every anchor.

IMPORTANT CAVEAT — this is a heuristic, not a determination. Receipts in
Ethiopia use both calendars, and nothing on the image reliably
distinguishes them. What we do have is a strong prior on the YEAR:
Ethiopian runs ~7-8 years behind Gregorian, so a receipt printed around
"now" carries an Ethiopian year around 2017-2019. A 4-digit 2020s year is
therefore almost certainly already Gregorian — clean computer-generated
invoices from corporate billing systems (the Ethio Telecom one, for
example) print Gregorian dates directly. parse_and_convert declines to
convert those rather than silently producing a real-but-wrong future
date, since 2026 Ethiopian is 2033 Gregorian.

Residual ambiguity this does NOT resolve: a genuine Ethiopian date in the
current Ethiopian year can still convert to a date a few months ahead
(current EC year 2019 began 11 Sept 2026, so its later months land in
2027). We accept that, because the raw text is always shown alongside the
converted value for a human to check.
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


def parse_and_convert(raw_text):
    """
    Best-effort conversion of a printed date like '16/12/18' or '16/12/2018'
    (dd/mm/yy or dd/mm/yyyy), read as Ethiopian. Returns an ISO date string,
    or None if it doesn't parse or the year is implausible as Ethiopian.

    A 4-digit year in the 2020s is almost certainly ALREADY Gregorian:
    Ethiopian years run ~7-8 behind Gregorian, so a receipt printed around
    "now" reads as 2017-2019 Ethiopian, not 2020+. Corporate billing systems
    (the Ethio Telecom invoice, for one) print Gregorian dates directly.
    Attempting to convert those as if they were Ethiopian silently produces
    a real-but-wrong future date -- 2026 Ethiopian is 2033 Gregorian --
    which is worse than showing nothing.

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
    if year >= 2020:
        return None
    try:
        return ethiopian_to_gregorian(year, month, day).isoformat()
    except (ValueError, OverflowError):
        return None
