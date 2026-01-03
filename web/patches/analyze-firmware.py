#!/usr/bin/env python3
"""
Firmware Patch Analyzer
Analyzes firmware binaries to determine safe maxLength values for patches
"""

import json
import sys


def analyze_string(firmware_path, search_string):
    """Analyze a string in the firmware and determine safe maxLength"""
    try:
        with open(firmware_path, "rb") as f:
            data = f.read()

        search_bytes = search_string.encode("utf-8")
        positions = []
        pos = 0

        # Find all occurrences
        while True:
            pos = data.find(search_bytes, pos)
            if pos == -1:
                break
            positions.append(pos)
            pos += 1

        if not positions:
            print(f"❌ String '{search_string}' not found in firmware")
            return None

        print(f"✓ Found {len(positions)} occurrence(s) of '{search_string}'")
        print()

        min_safe_length = float("inf")

        for i, pos in enumerate(positions):
            # Find the URL/context (look backwards for http://)
            url_start = data.rfind(b"http://", max(0, pos - 30), pos)
            if url_start == -1:
                url_start = max(0, pos - 20)

            # Find end of string (null byte or newline)
            url_end = pos + len(search_bytes)
            while url_end < len(data) and data[url_end] not in [0, ord("\n")]:
                url_end += 1

            # Count null bytes after
            null_count = 0
            temp_pos = url_end
            while temp_pos < len(data) and data[temp_pos] == 0:
                null_count += 1
                temp_pos += 1

            full_context = data[url_start:url_end]
            safe_length = len(search_bytes) + null_count

            print(f"Occurrence {i + 1} at position {pos}:")
            print(f"  Context: {full_context.decode('utf-8', errors='ignore')}")
            print(f"  String length: {len(search_bytes)} chars")
            print(f"  Null bytes after: {null_count}")
            print(f"  Max safe length: {safe_length} chars")
            print()

            min_safe_length = min(min_safe_length, safe_length)

        print(f"{'=' * 60}")
        print("RECOMMENDATION:")
        print(f"  String: {search_string}")
        print(f"  Conservative maxLength: {min_safe_length} chars")
        print("  (Based on shortest safe replacement across all occurrences)")
        print(f"{'=' * 60}")

        return {
            "find": search_string,
            "maxLength": min_safe_length,
            "occurrences": len(positions),
        }

    except Exception as e:
        print(f"❌ Error analyzing firmware: {e}")
        return None


def main():
    if len(sys.argv) < 3:
        print("Usage: analyze-firmware.py <firmware.bin> <string1> [string2] ...")
        print()
        print("Example:")
        print("  analyze-firmware.py firmware.bin '8.130.157.48' '47.122.74.33'")
        sys.exit(1)

    firmware_path = sys.argv[1]
    search_strings = sys.argv[2:]

    print(f"Analyzing: {firmware_path}")
    print(f"Searching for {len(search_strings)} string(s)")
    print("=" * 60)
    print()

    results = []
    for search_string in search_strings:
        result = analyze_string(firmware_path, search_string)
        if result:
            results.append(result)
        print()

    if results:
        print()
        print("JSON Output (for patch configuration):")
        print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
