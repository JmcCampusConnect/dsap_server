"""
Compatibility shims for the backend runtime.

Django 6 removed ``django.utils.baseconv``, but the installed
``django-cryptography`` package still imports it. We provide the tiny subset
that package needs so encrypted model fields can keep working in this codebase.
"""

from __future__ import annotations

import sys
import types


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
