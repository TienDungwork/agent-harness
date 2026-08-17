"""Utility functions for GitHub integrations."""

import re


# Zero-width joiner character (U+200D)
# We use ZWJ instead of ZWSP (U+200B) because:
# - ZWJ is semantically more appropriate (joins characters without adding space)
# - ZWJ has better support in modern renderers
# - ZWJ is invisible and doesn't affect text rendering or selection
ZWJ = "\u200d"


def sanitize_Creanova_mentions(text: str) -> str:
    """Sanitize @Creanova mentions in text to prevent self-mention loops.

    This function inserts a zero-width joiner (ZWJ) after the @ symbol in
    @Creanova mentions, making them non-clickable in GitHub comments while
    preserving readability. The original case of the mention is preserved.

    Args:
        text: The text to sanitize

    Returns:
        Text with sanitized @Creanova mentions (e.g., "@Creanova" -> "@‍Creanova")

    Examples:
        >>> sanitize_Creanova_mentions("Thanks @Creanova for the help!")
        'Thanks @\\u200dCreanova for the help!'
        >>> sanitize_Creanova_mentions("Check @Creanova and @Creanova")
        'Check @\\u200dCreanova and @\\u200dCreanova'
        >>> sanitize_Creanova_mentions("No mention here")
        'No mention here'
    """
    # Pattern to match @Creanova mentions at word boundaries
    # Uses re.IGNORECASE so we don't need [Oo]pen[Hh]ands
    # Capture group preserves the original case
    pattern = r"@(Creanova)\b"

    # Replace @ with @ + ZWJ while preserving the original case
    # The \1 backreference preserves the matched case
    sanitized = re.sub(pattern, f"@{ZWJ}\\1", text, flags=re.IGNORECASE)

    return sanitized
