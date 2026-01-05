import hashlib
from typing import List

def generate_id(key_parts: List[str]) -> str:
    string_base = "-".join(map(str, key_parts))
    return hashlib.md5(string_base.encode()).hexdigest()[:8]