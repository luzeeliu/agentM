#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test script to verify tool call parsing works correctly."""

import re
import json
import sys

# Fix encoding for Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

# Same patterns as in llm_core.py
TOOL_CALL_PATTERN = re.compile(
    r"<tool_call\s+name=[\"']?(?P<name>[\w\-_]+)[\"']?\s*>\s*(?P<args>\{.*?\})\s*</tool_call>",
    re.DOTALL | re.IGNORECASE,
)

TOOL_CALL_PATTERN_FALLBACK = re.compile(
    r"<tool_call\s+name=[\"']?(?P<name>[\w\-_]+)[\"']?\s*>\s*(?P<args>\{[^<]*?\})",
    re.DOTALL | re.IGNORECASE,
)

test_cases = [
    # Standard format
    '<tool_call name="google_search">{"query": "newest AI search paper"}</tool_call>',

    # Without quotes around name
    '<tool_call name=google_search>{"query": "test"}</tool_call>',

    # With single quotes
    "<tool_call name='google_search'>{'query': 'test'}</tool_call>",

    # With extra whitespace
    '<tool_call name="google_search">  {"query": "test"}  </tool_call>',

    # In a sentence
    'I will search for that. <tool_call name="google_search">{"query": "AI papers"}</tool_call> Let me find it.',

    # Hyphenated name
    '<tool_call name="web-search">{"query": "test"}</tool_call>',

    # WITHOUT CLOSING TAG (small model behavior)
    '<tool_call name="search_arxiv">{"query": "ai"}',

    # WITHOUT CLOSING TAG but with newline
    '<tool_call name="google_search">{"query": "test"}\n',
]

print("Testing tool call pattern matching:\n")

for i, test in enumerate(test_cases, 1):
    print(f"Test {i}: {test[:80]}...")

    # Try primary pattern first
    matches = list(TOOL_CALL_PATTERN.finditer(test))

    # Try fallback if primary fails
    used_fallback = False
    if not matches:
        matches = list(TOOL_CALL_PATTERN_FALLBACK.finditer(test))
        if matches:
            used_fallback = True

    if matches:
        status = "[OK - FALLBACK]" if used_fallback else "[OK]"
        print(f"  {status} Matched!")
        for match in matches:
            name = match.group("name")
            args = match.group("args")
            print(f"    - Tool: {name}")
            print(f"    - Args: {args}")
            try:
                parsed = json.loads(args)
                print(f"    - Parsed: {parsed}")
            except json.JSONDecodeError as e:
                print(f"    - JSON Error: {e}")
    else:
        print(f"  [FAIL] No match found!")
    print()
