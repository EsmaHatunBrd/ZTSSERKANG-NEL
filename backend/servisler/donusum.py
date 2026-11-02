"""Motor dataclass'ları ile JSON snapshot arasında dönüşüm. Decimal -> str, date -> ISO."""
from dataclasses import fields, is_dataclass
from datetime import date, datetime, timezone
from decimal import Decimal


def decimal_str(obj):
    if isinstance(obj, Decimal):
        return str(obj)
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    if is_dataclass(obj) and not isinstance(obj, type):
        return {f.name: decimal_str(getattr(obj, f.name)) for f in fields(obj)}
    if isinstance(obj, dict):
        return {str(k): decimal_str(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [decimal_str(v) for v in obj]
    return obj


def zaman_iso(zaman: datetime | None) -> str | None:
    """Saklanan zaman damgası UTC'dir (SQLite saat dilimi tutmaz); ISO çıktı her zaman +00:00 ofsetli."""
    if zaman is None:
        return None
    if zaman.tzinfo is None:
        zaman = zaman.replace(tzinfo=timezone.utc)
    return zaman.isoformat()


dataclass_to_dict = decimal_str
