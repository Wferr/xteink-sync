# Firmware Patch Definitions

This directory contains patch configuration files for different firmware versions.

## File Structure

Each firmware version has its own JSON file (e.g., `v3.1.5.json`) containing:
- Firmware metadata (version, filename, URL, checksums)
- List of patches to apply

## Patch Definition Format

```json
{
  "version": "V3.1.5",
  "filename": "V3.1.5_2-CH-X4.bin",
  "url": "http://example.com/firmware.bin",
  "size": 6279248,
  "checksums": {
    "crc32": "2F5E1957",
    "sha256": "fd86aa91932ec124f0e5fb711a74d1030c59796fec6e28e4b26e0a8ade8c57d1"
  },
  "patches": [
    {
      "name": "Service API Server",
      "description": "Main cloud service endpoint",
      "find": "8.130.157.48",
      "maxLength": 50,
      "required": true,
      "category": "network",
      "notes": "Additional context about this patch"
    }
  ]
}
```

## Field Descriptions

### Firmware Metadata
- `version`: Firmware version identifier
- `filename`: Original firmware filename
- `url`: Download URL for the firmware
- `size`: File size in bytes
- `checksums`: Verification checksums (CRC32, SHA256)

### Patch Fields
- `name`: Display name for the patch input
- `description`: User-friendly description shown in UI
- `find`: String to search for in the firmware binary
- `maxLength`: **Hard limit** - Maximum characters for replacement. This is determined by the original string length + available null bytes after it in the firmware binary. Exceeding this will corrupt adjacent data!
- `required`: Whether this patch is mandatory (true/false)
- `category`: Grouping category (e.g., "network", "mqtt", "api")
- `notes`: Additional documentation (optional)
- `enabled`: Default checkbox state (true/false, defaults to true)
- `occurrences`: Number of times the string appears in the firmware (informational)

## Adding New Patches

To add a new patch to an existing firmware version:

1. Open the corresponding JSON file (e.g., `v3.1.5.json`)
2. Add a new patch object to the `patches` array:

```json
{
  "name": "MQTT Broker",
  "description": "MQTT server endpoint",
  "find": "mqtt.xteink.com",
  "maxLength": 50,
  "required": false,
  "category": "mqtt",
  "notes": "Optional MQTT broker configuration"
}
```

3. Save the file - changes will be automatically picked up

## Adding New Firmware Versions

To add support for a new firmware version:

1. Create a new JSON file named `v{VERSION}.json` (e.g., `v3.2.0.json`)
2. Copy the structure from an existing version
3. Update all metadata and checksums
4. Define the patches for this version
5. Update `config.js` to point to the new version if needed

## Categories

Common patch categories:
- `network`: API servers, endpoints, IP addresses
- `mqtt`: MQTT broker configurations
- `wifi`: WiFi credentials or settings
- `cloud`: Cloud service endpoints
- `custom`: Custom user-defined patches

## Important Notes on maxLength

### ⚠️ HARD LIMITS - Cannot Be Extended! ⚠️

The `maxLength` values are **ABSOLUTE HARD LIMITS** that **CANNOT be increased** without modifying the firmware binary structure itself. Here's why:

#### Data Structure Analysis

The IP addresses are stored as null-terminated C strings embedded in larger URL strings:

```
Example from firmware binary:
http://8.130.157.48:5000/api/v1/sync/check\0\0X-Device-ID\0Content-Type...
      └─────────────┘                      └─┘
       12 chars (IP)                  2 null bytes padding
```

**Storage format:**
- Strings are null-terminated C strings (no length prefix)
- Null bytes (`\x00`) after each string are padding before the next data structure
- These null bytes are the ONLY extra space available
- The next data structure starts immediately after the padding

#### Why You Can't Make Them Longer

1. **No dynamic memory**: Strings are stored in the firmware's read-only data section
2. **Fixed layout**: The firmware binary has a fixed memory layout compiled into it
3. **Adjacent data**: Other data structures immediately follow the null padding
4. **Corruption risk**: Writing beyond the null bytes will corrupt adjacent data:
   - Headers (like "X-Device-ID", "Content-Type")
   - Other configuration strings
   - Function pointers
   - Critical firmware data

#### Example Breakdown

For `8.130.157.48`:
```
Position 6638759:
  Before: ...8Bhttp://
  String: 8.130.157.48        (12 bytes)
  Suffix: :5000/api/v1/sync/check
  After:  \0\0X-Device-ID\0
          └─┘ 2 null bytes = your ONLY extra space!
```

**Calculation:**
- Original IP: 12 chars
- Null padding: 2 bytes
- **maxLength: 14 chars (ABSOLUTE MAX)**

#### What Happens If You Exceed?

If you try to use a 15-character replacement:
```
Original:     8.130.157.48\0\0X-Device-ID
                          └─┘ null padding

Replacement:  my-server.com\0X-Device-ID
                           ^
                           This 'X' from your string overwrites
                           the first letter of "X-Device-ID"!
```

Result: **Corrupted firmware, device won't boot or behaves unpredictably**

#### To Determine maxLength for New Patches

Use the provided analyzer script:
```bash
python3 patches/analyze-firmware.py firmware.bin 'string-to-find'
```

Or manually:
```bash
python3 -c "
data = open('firmware.bin', 'rb').read()
target = b'string-to-find'
pos = data.find(target)
# Count null bytes after
null_count = 0
while data[pos + len(target) + null_count] == 0:
    null_count += 1
print(f'maxLength: {len(target) + null_count}')
"
```

#### Bottom Line

✅ **Safe**: Use replacements ≤ maxLength
❌ **UNSAFE**: Exceeding maxLength = firmware corruption
🔒 **Cannot increase**: These are hard limits from the binary structure

## General Notes

- The `find` string must exist exactly in the firmware binary
- Replacement values are padded with null bytes if shorter than the original
- All occurrences of the `find` string will be replaced
- ESP32 checksums are automatically recalculated after patching
- Each patch can be enabled/disabled via checkbox in the UI
- Only enabled patches with values will be applied
