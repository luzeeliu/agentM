# implement the kv storage for mapping each value by json
import os 
import json
import re
from .....log.logger import logger

def _sanitize_string_for_json(text: str) -> str:
    """Remove characters that cannot be encoded in UTF-8 for JSON serialization.

    Uses regex for optimal performance with zero-copy optimization for clean strings.
    Fast detection path for clean strings (99% of cases) with efficient removal for dirty strings.

    Args:
        text: String to sanitize

    Returns:
        Original string if clean (zero-copy), sanitized string if dirty
    """
    if not text:
        return text
    
    _SURROGATE_PATTERN = re.compile(r"[\uD800-\uDFFF\uFFFE\uFFFF]")
    # Fast path: Check if sanitization is needed using C-level regex search
    if not _SURROGATE_PATTERN.search(text):
        return text  # Zero-copy for clean strings - most common case

    # Slow path: Remove problematic characters using C-level regex substitution
    return _SURROGATE_PATTERN.sub("", text)

class SanitizingJSONEncoder(json.JSONEncoder):
    """
    Custom JSON encoder that sanitizes data during serialization.

    This encoder cleans strings during the encoding process without creating
    a full copy of the data structure, making it memory-efficient for large datasets.
    """

    def encode(self, o):
        """Override encode method to handle simple string cases"""
        if isinstance(o, str):
            return json.encoder.encode_basestring(_sanitize_string_for_json(o))
        return super().encode(o)

    def iterencode(self, o, _one_shot=False):
        """
        Override iterencode to sanitize strings during serialization.
        This is the core method that handles complex nested structures.
        """
        # Preprocess: sanitize all strings in the object
        sanitized = self._sanitize_for_encoding(o)

        # Call parent's iterencode with sanitized data
        for chunk in super().iterencode(sanitized, _one_shot):
            yield chunk

    def _sanitize_for_encoding(self, obj):
        """
        Recursively sanitize strings in an object.
        Creates new objects only when necessary to avoid deep copies.

        Args:
            obj: Object to sanitize

        Returns:
            Sanitized object with cleaned strings
        """
        if isinstance(obj, str):
            return _sanitize_string_for_json(obj)

        elif isinstance(obj, dict):
            # Create new dict with sanitized keys and values
            new_dict = {}
            for k, v in obj.items():
                clean_k = _sanitize_string_for_json(k) if isinstance(k, str) else k
                clean_v = self._sanitize_for_encoding(v)
                new_dict[clean_k] = clean_v
            return new_dict

        elif isinstance(obj, (list, tuple)):
            # Sanitize list/tuple elements
            cleaned = [self._sanitize_for_encoding(item) for item in obj]
            return type(obj)(cleaned) if isinstance(obj, tuple) else cleaned

        else:
            # Numbers, booleans, None, etc. remain unchanged
            return obj
        



def load_json(file_name):
    if not os.path.exists(file_name):
        return None
    with open(file_name, encoding="utf-8-sig") as f:
        return json.load(f)
    
def write_json(json_obj, file_name):
    """
    Write JSON data to file with optimized sanitization strategy.

    This function uses a two-stage approach:
    1. Fast path: Try direct serialization (works for clean data ~99% of time)
    2. Slow path: Use custom encoder that sanitizes during serialization

    The custom encoder approach avoids creating a deep copy of the data,
    making it memory-efficient. When sanitization occurs, the caller should
    reload the cleaned data from the file to update shared memory.

    Args:
        json_obj: Object to serialize (may be a shallow copy from shared memory)
        file_name: Output file path

    Returns:
        bool: True if sanitization was applied (caller should reload data),
              False if direct write succeeded (no reload needed)
    """
    try:
        with open(file_name, "w", encoding="utf-8") as f:
            json.dump(json_obj, f, ensure_ascii=False, indent=2)
        
        return False  # No sanitization needed
    except (UnicodeDecodeError, UnicodeEncodeError) as e:
        logger.debug(f"Direct JSON write failed, applying sanitization: {e}")
        
        with open(file_name, "w", encoding="utf-8") as f:
            json.dump(json_obj, f, cls=SanitizingJSONEncoder, ensure_ascii=False, indent=2)
        
        logger.info(f"Sanitization applied, please reload data from {file_name} to update shared memory.")
        return True  # Sanitization was applied
    
