# Part of custom_hr_contract. See LICENSE file for full copyright and licensing details.
"""Pure Python Vietnamese currency number-to-words converter.

Zero external dependencies. Handles integers from 0 to 999,999,999,999,999
(up to hundreds of trillions), which covers any practical VND salary.

Usage::

    >>> from odoo.addons.custom_hr_contract.tools.vietnamese_converter import num_to_words_vi
    >>> num_to_words_vi(15000000)
    'Mười lăm triệu đồng chẵn'
    >>> num_to_words_vi(0)
    'Không đồng chẵn'
    >>> num_to_words_vi(1500)
    'Một nghìn năm trăm đồng chẵn'
"""

_DIGITS = [
    '', 'một', 'hai', 'ba', 'bốn',
    'năm', 'sáu', 'bảy', 'tám', 'chín',
]

_GROUPS = [
    '', 'nghìn', 'triệu', 'tỷ', 'nghìn tỷ', 'triệu tỷ',
]


def _read_three(n, has_higher_group=False):
    """Convert a 3-digit group ``n`` (0–999) to Vietnamese words.

    ``has_higher_group`` is True when a non-zero group precedes this one,
    which affects the reading of tens and units (e.g. "lẻ", "linh").
    """
    if n == 0:
        return ''

    hundreds = n // 100
    remainder = n % 100
    tens = remainder // 10
    units = remainder % 10
    parts = []

    if hundreds:
        parts.append(f'{_DIGITS[hundreds]} trăm')
    elif has_higher_group:
        # Zero hundreds with a preceding group → add "không trăm"
        parts.append('không trăm')

    if tens == 0 and units != 0:
        # Units without tens → "lẻ" (or "linh")
        if hundreds or has_higher_group:
            parts.append('lẻ')
        if units == 1:
            parts.append('một')
        elif units == 5:
            parts.append('năm')
        else:
            parts.append(_DIGITS[units])
    elif tens == 1:
        parts.append('mười')
        if units == 1:
            parts.append('một')
        elif units == 5:
            parts.append('lăm')
        elif units:
            parts.append(_DIGITS[units])
    elif tens >= 2:
        parts.append(f'{_DIGITS[tens]} mươi')
        if units == 1:
            parts.append('mốt')
        elif units == 4:
            parts.append('tư')
        elif units == 5:
            parts.append('lăm')
        elif units:
            parts.append(_DIGITS[units])

    return ' '.join(parts)


def num_to_words_vi(amount, currency='đồng', suffix='chẵn'):
    """Convert ``amount`` (int or float) to Vietnamese words.

    Negative amounts are prefixed with "Âm".  Fractional parts are
    silently truncated (VND has no subunit in everyday use).

    Parameters
    ----------
    amount : int | float
        The monetary amount.
    currency : str
        The currency word appended after the number (default ``'đồng'``).
    suffix : str
        Word appended at the very end for exact amounts (default ``'chẵn'``).
        Pass ``''`` to omit.

    Returns
    -------
    str
        Human-readable Vietnamese reading, first letter capitalised.

    Raises
    ------
    ValueError
        If *amount* exceeds the supported range.
    """
    if not isinstance(amount, (int, float)):
        raise TypeError(f"amount must be int or float, got {type(amount).__name__}")

    negative = amount < 0
    amount = int(abs(amount))

    if amount == 0:
        result = 'không'
    else:
        # Split into groups of 3 digits from the right
        groups = []
        temp = amount
        while temp > 0:
            groups.append(temp % 1000)
            temp //= 1000

        if len(groups) > len(_GROUPS):
            raise ValueError(
                f"Amount {amount} is too large. Maximum supported: "
                f"{'9' * (len(_GROUPS) * 3)} ({len(_GROUPS) * 3} digits)"
            )

        # Build from the highest group to the lowest
        parts = []
        for i in range(len(groups) - 1, -1, -1):
            group_val = groups[i]
            if group_val == 0:
                continue
            has_higher = any(groups[j] != 0 for j in range(i + 1, len(groups)))
            text = _read_three(group_val, has_higher_group=has_higher)
            group_name = _GROUPS[i]
            if group_name:
                parts.append(f'{text} {group_name}')
            else:
                parts.append(text)

        result = ' '.join(parts)

    # Build the final string
    final_parts = []
    if negative:
        final_parts.append('âm')
    final_parts.append(result)
    if currency:
        final_parts.append(currency)
    if suffix:
        final_parts.append(suffix)

    text = ' '.join(final_parts)
    # Capitalise first letter
    return text[0].upper() + text[1:]
