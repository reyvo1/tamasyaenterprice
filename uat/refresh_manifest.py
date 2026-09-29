"""Regenerate source manifest after an explicitly reviewed source edit."""
from pathlib import Path
import hashlib
src=Path(__file__).resolve().parents[1]/'work/enterprise'
paths=sorted(p for p in src.rglob('*') if p.is_file() and p.name!='FILE_CHECKSUMS.sha256')
(src/'FILE_CHECKSUMS.sha256').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.relative_to(src).as_posix()+'\n' for p in paths))
