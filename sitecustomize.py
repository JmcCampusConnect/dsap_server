"""
Compatibility shims for the backend runtime.

Django 6 removed ``django.utils.baseconv``, but the installed
``django-cryptography`` package still imports it. We provide the tiny subset
that package needs so encrypted model fields can keep working in this codebase.
"""

from __future__ import annotations

import os
from pathlib import Path
import sys
import types

# Ensure PostgreSQL client library (libpq) is discoverable by psycopg on Windows
if sys.platform == 'win32':
    pg_base = Path(r'C:\Program Files\PostgreSQL')
    if pg_base.is_dir():
        for version_dir in sorted(pg_base.iterdir(), reverse=True):
            bin_dir = version_dir / 'bin'
            if (bin_dir / 'libpq.dll').is_file():
                candidate = str(bin_dir)
                if candidate not in os.environ.get('PATH', ''):
                    os.environ['PATH'] = candidate + os.pathsep + os.environ.get('PATH', '')
                try:
                    os.add_dll_directory(candidate)
                except OSError:
                    pass
                break


def _make_base62_module() -> types.ModuleType:
    alphabet = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
    base = len(alphabet)

    def encode(number: int) -> str:
        if number == 0:
            return alphabet[0]
        if number < 0:
            raise ValueError('base62 only supports non-negative integers')

        digits = []
        while number:
            number, remainder = divmod(number, base)
            digits.append(alphabet[remainder])
        return ''.join(reversed(digits))

    def decode(value: str) -> int:
        result = 0
        for char in value:
            result = result * base + alphabet.index(char)
        return result

    module = types.ModuleType('django.utils.baseconv')
    module.base62 = types.SimpleNamespace(encode=encode, decode=decode)
    return module


if 'django.utils.baseconv' not in sys.modules:
    sys.modules['django.utils.baseconv'] = _make_base62_module()
