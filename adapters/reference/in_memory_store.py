from __future__ import annotations

import hashlib


class InMemoryObjectStore:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    async def put(self, namespace: str, content: bytes) -> str:
        digest = hashlib.sha256(content).hexdigest()
        location = f"memory://{namespace}/{digest}"
        self.objects[location] = bytes(content)
        return location

    async def get(self, location: str) -> bytes:
        return self.objects[location]

    async def delete(self, location: str) -> str:
        self.objects.pop(location, None)
        return hashlib.sha256(location.encode()).hexdigest()
