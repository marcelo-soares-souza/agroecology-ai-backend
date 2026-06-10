from __future__ import annotations

import os
import time


def uuid7() -> str:
    ts = int(time.time() * 1000)
    rand = os.urandom(10)
    ts_bytes = ts.to_bytes(6, "big")
    b = bytearray(ts_bytes + rand)
    b[6] = (b[6] & 0x0F) | 0x70
    b[8] = (b[8] & 0x3F) | 0x80
    return (
        f"{int.from_bytes(b[0:4], 'big'):08x}-"
        f"{int.from_bytes(b[4:6], 'big'):04x}-"
        f"{b[6]:02x}{b[7]:02x}-"
        f"{b[8]:02x}{b[9]:02x}-"
        f"{b[10:].hex()}"
    )
