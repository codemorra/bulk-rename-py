"""Token processing and mask application.

Handles replacement of placeholder tokens in filename masks,
supporting tokens like {name}, {ext}, {counter}, {date}, {time},
and their variants with slicing (e.g., {name1-3}, {ext1-2}).
"""

import re
from datetime import datetime
from pathlib import Path

# Patterns
_LITERAL_BRACES_PATTERN = re.compile(r'\{\{\}([^{}]+)\{\}\}')
_TOKEN_PATTERN = re.compile(r'\{([^\{\}]+)\}')


class TokenProcessor:
    """Token processing and mask application operations.

    Handles replacement of placeholder tokens in filename masks.

    All methods are static as no instance state is required.
    """


######################
# MAIN FUNCTIONALITY #
######################
    @staticmethod
    def apply_name_mask(
            mask: str,
            oname: str,
            ext: str,
            counter: str,
            date_str: str,
            time_str: str,
            path: Path | None = None,
            date_type: str = 'current',
            timestamp: datetime | None = None
    ) -> str:
        """Apply placeholders in name mask.

        Replaces tokens like {name}, {ext}, {counter}, {date}, {time} with actual values.

        **Parameters:**
            `mask` (str): Name mask with placeholders
            `oname` (str): Original base name
            `ext` (str): Original file extension
            `counter` (str): Formatted counter
            `date_str` (str): Formatted date
            `time_str` (str): Formatted time
            `path` (Path | None): File path for date_type='change'
            `date_type` (str): Date source ("current" or "change")
            `timestamp` (datetime | None): Shared timestamp supplied by the preview

        **Returns:**
            `str`: Result after applying mask

        **Supported tokens:**
            {name}, {nameX-Y}: Current filename with optional slicing
            {ext}, {extX-Y}: File extension with optional slicing
            {counter}: Numeric counter
            {date}: Date string
            {time}: Time string
        """
        # Escape literal braces to prevent them from being processed as tokens
        esc_mask, litmap = TokenProcessor._escape_literal_braces(mask)

        def _repl(m: re.Match) -> str:
            nonlocal timestamp
            tok = m.group(1)

            # Handle {name} and {nameX-Y} tokens
            if tok == 'name':
                return oname
            if tok.startswith('name'):
                spec = tok[4:]
                if spec and re.fullmatch(r'(\d+|\*)-(\d+|\*)', spec):
                    return TokenProcessor._slice_token(oname, spec)
                return f'{{{tok}}}'

            # Handle {ext} and {extX-Y} tokens
            if tok == 'ext':
                return ext
            if tok.startswith('ext'):
                spec = tok[3:]
                if spec and re.fullmatch(r'(\d+|\*)-(\d+|\*)', spec):
                    return TokenProcessor._slice_token(ext, spec)
                return f'{{{tok}}}'

            # Handle simple tokens
            if tok == 'counter':
                return counter
            if tok == 'date':
                return date_str
            if tok == 'time':
                return time_str

            # Handle custom date/time format patterns
            is_date = TokenProcessor._is_custom_date_format(tok)
            is_time = TokenProcessor._is_custom_time_format(tok)
            if is_date or is_time:
                if timestamp is None:
                    timestamp = TokenProcessor.get_datetime(path, date_type)
                if is_date:
                    return TokenProcessor._format_custom_date(tok, timestamp)
                return TokenProcessor._format_custom_time(tok, timestamp)

            # Return unknown tokens unchanged
            return f'{{{tok}}}'

        # Apply token replacement and restore literal braces
        result = _TOKEN_PATTERN.sub(_repl, esc_mask)
        result = TokenProcessor._restore_literal_braces(result, litmap)

        return result

    @staticmethod
    def apply_case_transform(text: str, mode: str) -> str:
        """Apply case transformation to text.

        **Parameters:**
            `text` (str): Text to transform
            `mode` (str): Transformation mode

        **Returns:**
            `str`: Transformed text

        **Supported modes:**
            lowercase: Convert to lowercase
            uppercase: Convert to uppercase
            heading: Capitalize first letter
            mocking: AlTeRnAtInG cAsE
            other: Return unchanged
        """
        # Apply case transformation based on mode
        if mode == 'lowercase':
            return text.lower()
        elif mode == 'uppercase':
            return text.upper()
        elif mode == 'heading':
            return text.capitalize()
        elif mode == 'mocking':
            # Create alternating case pattern
            return ''.join(
                ch.upper() if i % 2 == 0 else ch.lower()
                for i, ch in enumerate(text)
            )
        return text


##################
# HELPER METHODS #
##################
    @staticmethod
    def _escape_literal_braces(mask: str) -> tuple[str, dict[str, str]]:
        """Escape literal brace segments in mask.

        Converts segments like {{}name{}} to temporary placeholders.

        **Parameters:**
            `mask` (str): Input mask containing tokens and literal braces

        **Returns:**
            `tuple[str, dict[str, str]]`: Modified mask and mapping of placeholders to original content
        """
        litmap = {}

        def _repl(m: re.Match) -> str:
            key = f"__LITERAL_{len(litmap)}__"
            litmap[key] = m.group(0)
            return key

        return _LITERAL_BRACES_PATTERN.sub(_repl, mask), litmap

    @staticmethod
    def _restore_literal_braces(text: str, mapping: dict[str, str]) -> str:
        """Restore literal brace markers.

        **Parameters:**
            `text` (str): Text containing __LITERAL_i__ markers
            `mapping` (dict[str, str]): Placeholder to original literal mapping

        **Returns:**
            `str`: Text with restored literal braces
        """
        for key, val in mapping.items():
            text = text.replace(key, val)

        return text

    @staticmethod
    def _slice_token(text: str, spec: str) -> str:
        """Extract substring using range specification.

        **Parameters:**
            `text` (str): Source text
            `spec` (str): Range specification (start-end)

        **Returns:**
            `str`: Extracted substring or original text if invalid

        **Examples:**
            "1-3" → characters 1 to 3
            "4-*" → from character 4 to end
            "*-5" → from start to character 5
            "*-*" → full text
        """
        # Parse range specification and extract substring
        spec = spec.strip()
        m = re.fullmatch(r'(\d+|\*)-(\d+|\*)', spec)
        if not m:
            return text
        
        # Convert range specification to indices
        left, right = m.groups()
        start = 1 if left == '*' else max(1, int(left))
        end = len(text) if right == '*' else int(right)
        
        # Return sliced substring (Python uses 0-based indexing)
        return text[start-1:end]

    @staticmethod
    def _is_custom_date_format(tok: str) -> bool:
        """Check if token is a custom date format.

        **Parameters:**
            `tok` (str): Token to check

        **Returns:**
            `bool`: True if token matches custom date format pattern
        """
        # Check for patterns like yyyy-mm-dd, dd.mm.yyyy, yyyymmdd, etc.
        # Support separators: - _ . ; space : or no separator
        return bool(re.fullmatch(r'(yyyy|yy|mm|dd)(?:[\-._; :]?(?:yyyy|yy|mm|dd)){0,2}', tok))

    @staticmethod
    def _is_custom_time_format(tok: str) -> bool:
        """Check if token is a custom time format.

        **Parameters:**
            `tok` (str): Token to check

        **Returns:**
            `bool`: True if token matches custom time format pattern
        """
        # Check for patterns like hh-mm-ss, hh.mm, hhmmss, etc.
        # Support separators: - _ . ; space : or no separator
        return (bool(re.fullmatch(r'(hh|mm|ss)([\-._; :]?)(hh|mm|ss)([\-._; :]?)(hh|mm|ss)', tok)) or
                bool(re.fullmatch(r'(hh|mm|ss)([\-._; :]?)(hh|mm|ss)', tok)) or
                bool(re.fullmatch(r'(hh|mm|ss)', tok)))

    @staticmethod
    def get_datetime(path: Path | None, date_type: str, now: datetime | None = None) -> datetime:
        """Resolve a file timestamp with a shared current-time fallback.

        **Parameters:**
            `path` (Path | None): Source file for modification time
            `date_type` (str): Date source ("current" or "change")
            `now` (datetime | None): Current time shared across a preview

        **Returns:**
            `datetime`: File modification time or the supplied current time
        """
        current = now if now is not None else datetime.now()
        if date_type == 'change' and path is not None:
            try:
                return datetime.fromtimestamp(path.stat().st_mtime)
            except (OSError, OverflowError, ValueError):
                return current
        return current

    @staticmethod
    def _format_custom_date(format_pattern: str, timestamp: datetime) -> str:
        """Format a custom date token using the shared file timestamp.

        **Parameters:**
            `format_pattern` (str): Custom format pattern (e.g., 'yyyy-mm-dd')
            `timestamp` (datetime): Timestamp resolved for the source file

        **Returns:**
            `str`: Formatted date string
        """
        pattern = format_pattern.replace('yyyy', '%Y').replace('yy', '%y')
        pattern = pattern.replace('mm', '%m').replace('dd', '%d')
        return timestamp.strftime(pattern)

    @staticmethod
    def _format_custom_time(format_pattern: str, timestamp: datetime) -> str:
        """Format a custom time token using the shared file timestamp.

        **Parameters:**
            `format_pattern` (str): Custom format pattern (e.g., 'hh-mm-ss')
            `timestamp` (datetime): Timestamp resolved for the source file

        **Returns:**
            `str`: Formatted time string
        """
        pattern = format_pattern.replace('hh', '%H').replace('mm', '%M').replace('ss', '%S')
        return timestamp.strftime(pattern)
