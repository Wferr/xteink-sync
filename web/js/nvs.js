// ========================================================================
// NVS PARSER (Ported from firmware/parse_nvs.py)
// ========================================================================

import { log } from "./utils.js";

const PAGE_SIZE = 4096;

// Entry Types
const NVS_TYPE_U8 = 0x01;
const NVS_TYPE_I8 = 0x11;
const NVS_TYPE_U16 = 0x02;
const NVS_TYPE_I16 = 0x12;
const NVS_TYPE_U32 = 0x04;
const NVS_TYPE_I32 = 0x14;
const NVS_TYPE_U64 = 0x08;
const NVS_TYPE_I64 = 0x18;
const NVS_TYPE_STR = 0x21;
const NVS_TYPE_BLOB = 0x41;
const NVS_TYPE_ANY = 0xff;

const TypeNames = {
  [NVS_TYPE_U8]: "U8",
  [NVS_TYPE_I8]: "I8",
  [NVS_TYPE_U16]: "U16",
  [NVS_TYPE_I16]: "I16",
  [NVS_TYPE_U32]: "U32",
  [NVS_TYPE_I32]: "I32",
  [NVS_TYPE_U64]: "U64",
  [NVS_TYPE_I64]: "I64",
  [NVS_TYPE_STR]: "STR",
  [NVS_TYPE_BLOB]: "BLOB",
  [NVS_TYPE_ANY]: "ANY",
};

export async function readNvsPartition(esploader) {
  try {
    log("Scanning partition table for NVS...", "info");

    const PARTITION_TABLE_OFFSET = 0x8000;
    const PARTITION_TABLE_SIZE = 0xc00;

    // Read as raw data (ArrayBuffer/String depending on loader)
    const rawData = await esploader.readFlash(
      PARTITION_TABLE_OFFSET,
      PARTITION_TABLE_SIZE,
    );
    const binaryData = new Uint8Array(rawData); // Convert to typed array for reliable indexing

    let offset = 0;
    let nvsPartition = null;

    // Parse partition table
    while (offset < binaryData.length) {
      // Magic 0xAA50 (Little Endian in memory: 50 AA) ...
      // Wait, binary partition table magic is 0x50AA.
      // ota.js does: const magic = (data[offset + 1] << 8) | data[offset]; if (magic !== 0x50AA) break;

      const magic = (binaryData[offset + 1] << 8) | binaryData[offset];
      if (magic !== 0x50aa) {
        break;
      }

      const type = binaryData[offset + 2];
      const subtype = binaryData[offset + 3];

      if (type === 0x01 && subtype === 0x02) {
        // Type data, subtype nvs
        // Found NVS
        // Offsets are uint32 little endian
        const partOffset =
          binaryData[offset + 4] |
          (binaryData[offset + 5] << 8) |
          (binaryData[offset + 6] << 16) |
          (binaryData[offset + 7] << 24);

        const partSize =
          binaryData[offset + 8] |
          (binaryData[offset + 9] << 8) |
          (binaryData[offset + 10] << 16) |
          (binaryData[offset + 11] << 24);

        nvsPartition = { offset: partOffset, size: partSize };
        break;
      }
      offset += 32;
    }

    if (!nvsPartition) {
      log("No NVS partition found.", "warning");
      const container = document.getElementById("nvsDataContainer");
      if (container)
        container.innerHTML =
          "<p>No NVS partition found in partition table.</p>";
      return;
    }

    log(
      `Found NVS partition at 0x${nvsPartition.offset.toString(16)} (Size: ${nvsPartition.size})`,
      "info",
    );
    log("Reading NVS data...", "info");

    const nvsRaw = await esploader.readFlash(
      nvsPartition.offset,
      nvsPartition.size,
    );
    const nvsBytes = new Uint8Array(nvsRaw);

    const entries = parseNvsData(nvsBytes);
    renderNvsTable(entries);
  } catch (e) {
    log(`Error reading NVS: ${e.message}`, "error");
    log("Error reading NVS: " + e.message, "error");
  }
}

function parseNvsData(data) {
  const pageCount = Math.floor(data.length / PAGE_SIZE);
  const pages = [];

  // 1. Scan/Parse all pages first to get their sequence numbers
  for (let i = 0; i < pageCount; i++) {
    const pageStart = i * PAGE_SIZE;
    const pageData = data.subarray(pageStart, pageStart + PAGE_SIZE);

    // Header: State(0-4), Seq(4-8)
    const state =
      (pageData[0] |
        (pageData[1] << 8) |
        (pageData[2] << 16) |
        (pageData[3] << 24)) >>>
      0;
    const seq =
      (pageData[4] |
        (pageData[5] << 8) |
        (pageData[6] << 16) |
        (pageData[7] << 24)) >>>
      0;

    // 0xFFFFFFFF = Empty, 0xFFFFFFFE = Active, 0xFFFFFFFC = Full
    if (state === 0xfffffffe || state === 0xfffffffc) {
      pages.push({
        index: i,
        seq: seq,
        data: pageData,
      });
    }
  }

  // 2. Sort pages by Sequence Number to process history correctly
  pages.sort((a, b) => a.seq - b.seq);

  // 3. Parse entries and deduplicate using a Map (Latest overwrites previous)
  // Key format: "NamespaceIndex:KeyName"
  const entryMap = new Map();

  for (const page of pages) {
    const pageEntries = parseNvsPage(page.data, page.index);
    for (const entry of pageEntries) {
      // Unique key for NVS is Namespace + Key string
      const uniqueId = `${entry.ns}:${entry.key}`;
      entryMap.set(uniqueId, entry);
    }
  }

  return Array.from(entryMap.values());
}

function parseNvsPage(pageData, pageIndex) {
  // We already checked the header in the main loop
  const entries = [];
  let offset = 64; // Skip header (32) and bitmap (32)

  const textDecoder = new TextDecoder("utf-8");

  while (offset < PAGE_SIZE) {
    // Read entry metadata (Namespace, Type, Span, Chunk)
    const ns = pageData[offset];
    const type = pageData[offset + 1];
    const span = pageData[offset + 2];

    if (ns === 0xff) {
      // Empty/erased entry
      offset += 32;
      continue;
    }

    // Read Key (16 bytes, null terminated)
    // Slice 8 bytes offset for key
    let keyBytes = pageData.subarray(offset + 8, offset + 24);
    // Find null terminator
    let nullIdx = keyBytes.indexOf(0);
    if (nullIdx >= 0) keyBytes = keyBytes.subarray(0, nullIdx);
    const key = textDecoder.decode(keyBytes);

    let value = "<?>";
    const valueOffset = offset + 24; // 8 bytes of inline data

    // Handle types
    if (type === NVS_TYPE_U8) value = pageData[valueOffset];
    else if (type === NVS_TYPE_I8) {
      let val = pageData[valueOffset];
      if (val > 127) val -= 256;
      value = val;
    } else if (type === NVS_TYPE_U16)
      value = pageData[valueOffset] | (pageData[valueOffset + 1] << 8);
    else if (type === NVS_TYPE_U32) {
      value =
        (pageData[valueOffset] |
          (pageData[valueOffset + 1] << 8) |
          (pageData[valueOffset + 2] << 16) |
          (pageData[valueOffset + 3] << 24)) >>>
        0;
    } else if (type === NVS_TYPE_STR) {
      // String data starts at the NEXT entry (offset + 32)
      // It spans 'span' entries
      // Each entry is 32 bytes
      const dataStart = offset + 32;
      const dataEnd = offset + 32 * span;

      if (dataEnd <= PAGE_SIZE) {
        let strBytes = pageData.subarray(dataStart, dataEnd);
        let strNull = strBytes.indexOf(0);
        if (strNull >= 0) strBytes = strBytes.subarray(0, strNull);
        value = `"${textDecoder.decode(strBytes)}"`;
      } else {
        value = "<PageOverflow>";
      }
    } else if (type === NVS_TYPE_BLOB) {
      const dataStart = offset + 32;
      const dataEnd = offset + 32 * span;
      if (dataEnd <= PAGE_SIZE) {
        let hex = "";
        // Show first 8 bytes
        const maxLen = Math.min(8, dataEnd - dataStart);
        for (let j = 0; j < maxLen; j++) {
          hex += pageData[dataStart + j].toString(16).padStart(2, "0");
        }
        if (dataEnd - dataStart > 8) hex += "...";
        value = `<Blob: ${hex}>`;
      }
    }

    // Only add valid types
    if (type !== 0xff && TypeNames[type]) {
      entries.push({
        page: pageIndex,
        ns: ns,
        type: TypeNames[type],
        key: key,
        value: value,
      });
    }

    // Move to next entry (skipping spans)
    offset += 32 * span;
  }

  return entries;
}

function renderNvsTable(entries) {
  const container = document.getElementById("nvsDataContainer");
  if (!container) return;

  if (entries.length === 0) {
    container.innerHTML = "<p>No valid NVS data found.</p>";
    return;
  }

  let html =
    '<table class="striped"><thead><tr><th>Key</th><th>Type</th><th>Value</th></tr></thead><tbody>';

  // Sort by Key
  entries.sort((a, b) => a.key.localeCompare(b.key));

  entries.forEach((e) => {
    html += `<tr>
            <td><code>${e.key}</code></td>
            <td>${e.type}</td>
            <td><code>${e.value}</code></td>
        </tr>`;
  });
  html += "</tbody></table>";

  container.innerHTML = html;
}
