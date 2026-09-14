from datetime import datetime
from flask import session

SUPPORTED_DATE_FORMATS = {
    "YYYY-MM-DD": "%Y-%m-%d",
    "DD-MM-YYYY": "%d-%m-%Y",
    "MM-DD-YYYY": "%m-%d-%Y",
    "DD/MM/YYYY": "%d/%m/%Y",
    "MM/DD/YYYY": "%m/%d/%Y",
    "DD MMM YYYY": "%d %b %Y"
}

DEFAULT_DATE_FORMAT = "YYYY-MM-DD"

def format_date_filter(value, date_format_name=None):
    """
    Jinja template filter & Python helper to format date strings or datetime objects
    according to the Admin-selected Date Format setting.
    Falls back to 'YYYY-MM-DD' if unconfigured or invalid.
    """
    if not value:
        return ""

    if date_format_name is None:
        try:
            date_format_name = session.get("date_format", DEFAULT_DATE_FORMAT)
        except Exception:
            date_format_name = DEFAULT_DATE_FORMAT

    fmt_pattern = SUPPORTED_DATE_FORMATS.get(date_format_name, "%Y-%m-%d")

    dt = None
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        val_clean = value.strip()

        for parse_fmt in [
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
            "%d-%m-%Y",
            "%m-%d-%Y",
            "%d/%m/%Y",
            "%m/%d/%Y"
        ]:
            try:
                dt = datetime.strptime(val_clean, parse_fmt)
                break
            except (ValueError, TypeError):
                pass
        
        if not dt and ("T" in val_clean or " " in val_clean):
            val_clean_date = val_clean.split("T")[0].split(" ")[0]
            try:
                dt = datetime.strptime(val_clean_date, "%Y-%m-%d")
            except (ValueError, TypeError):
                pass

    if dt:
        return dt.strftime(fmt_pattern)

    return str(value)
