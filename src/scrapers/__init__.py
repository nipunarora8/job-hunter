import hashlib

def make_slug(source: str, identifier: str) -> str:
    return hashlib.md5(f"{source}:{identifier}".encode()).hexdigest()
