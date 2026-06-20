from __future__ import annotations

import base64
import ctypes
from ctypes import wintypes


CRYPTPROTECT_UI_FORBIDDEN = 0x01


class DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]


crypt32 = ctypes.windll.crypt32
kernel32 = ctypes.windll.kernel32


def _bytes_to_blob(data: bytes) -> DATA_BLOB:
    blob = DATA_BLOB()
    blob.cbData = len(data)
    blob.pbData = ctypes.cast(ctypes.create_string_buffer(data), ctypes.POINTER(ctypes.c_byte))
    return blob


def _blob_to_bytes(blob: DATA_BLOB) -> bytes:
    if not blob.cbData:
        return b""
    ptr = ctypes.cast(blob.pbData, ctypes.POINTER(ctypes.c_char))
    data = ctypes.string_at(ptr, blob.cbData)
    kernel32.LocalFree(blob.pbData)
    return data


def protect_bytes(data: bytes) -> bytes:
    in_blob = _bytes_to_blob(data)
    out_blob = DATA_BLOB()
    ok = crypt32.CryptProtectData(
        ctypes.byref(in_blob),
        None,
        None,
        None,
        None,
        CRYPTPROTECT_UI_FORBIDDEN,
        ctypes.byref(out_blob),
    )
    if not ok:
        raise ctypes.WinError()
    return _blob_to_bytes(out_blob)


def unprotect_bytes(data: bytes) -> bytes:
    in_blob = _bytes_to_blob(data)
    out_blob = DATA_BLOB()
    ok = crypt32.CryptUnprotectData(
        ctypes.byref(in_blob),
        None,
        None,
        None,
        None,
        CRYPTPROTECT_UI_FORBIDDEN,
        ctypes.byref(out_blob),
    )
    if not ok:
        raise ctypes.WinError()
    return _blob_to_bytes(out_blob)


def protect_text(text: str) -> str:
    encrypted = protect_bytes(text.encode("utf-8"))
    return base64.b64encode(encrypted).decode("ascii")


def unprotect_text(encoded: str) -> str:
    encrypted = base64.b64decode(encoded.encode("ascii"))
    return unprotect_bytes(encrypted).decode("utf-8")
