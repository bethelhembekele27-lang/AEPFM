import os

ALLOWED = {'.pdf', '.jpg', '.jpeg', '.png', '.gif', '.webp', '.doc', '.docx', '.xls', '.xlsx', '.csv', '.txt'}
IMAGES = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
MAX_BYTES = 10 * 1024 * 1024


def validate_staff_upload(f):
    if f is None:
        return 'A file is required.'
    if f.size > MAX_BYTES:
        return 'File is larger than 10 MB.'
    ext = os.path.splitext(f.name)[1].lower()
    if ext not in ALLOWED:
        return f'File type {ext or "(none)"} is not allowed.'
    head = f.read(8); f.seek(0)
    if ext == '.pdf' and not head.startswith(b'%PDF-'):
        return 'This is not a valid PDF.'
    if ext in {'.docx', '.xlsx'} and not head.startswith(b'PK'):
        return 'This is not a valid Office file.'
    if ext in IMAGES:
        try:
            from PIL import Image
            Image.open(f).verify()
        except Exception:
            return 'This is not a valid image.'
        finally:
            f.seek(0)
    return None
