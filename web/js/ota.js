// ========================================================================
// OTA PARTITION MANAGEMENT
// Reference: ESP-IDF v4.4.7
// - Structure: components/bootloader_support/include/esp_flash_partitions.h
// - CRC Logic: components/bootloader_support/src/bootloader_common_loader.c
// - Source: https://github.com/espressif/esp-idf/tree/v4.4.7
// ========================================================================

import { log, calculateCRC32, uint8ArrayToString } from "./utils.js";

let partitions = [];

// Parse partition table
function parsePartitionTable(data) {
  const partitions = [];
  let offset = 0;

  while (offset < data.length) {
    const magic = (data[offset + 1] << 8) | data[offset];
    if (magic !== 0x50aa) break;

    const type = data[offset + 2];
    const subtype = data[offset + 3];
    const pos_offset = new DataView(
      data.buffer,
      data.byteOffset + offset + 4,
      4,
    ).getUint32(0, true);
    const size = new DataView(
      data.buffer,
      data.byteOffset + offset + 8,
      4,
    ).getUint32(0, true);

    const labelBytes = data.slice(offset + 12, offset + 28);
    const label = new TextDecoder().decode(labelBytes).replace(/\0/g, "");

    const typeNames = { 0: "app", 1: "data" };
    const subtypeNames = {
      "0-0": "factory",
      "0-16": "ota_0",
      "0-17": "ota_1",
      "1-0": "otadata",
      "1-1": "phy",
      "1-2": "nvs",
      "1-130": "spiffs",
    };

    partitions.push({
      type,
      subtype,
      offset: pos_offset,
      size,
      label,
      typeName: typeNames[type] || "unknown",
      subtypeName:
        subtypeNames[`${type}-${subtype}`] || `0x${subtype.toString(16)}`,
    });

    offset += 32;
  }

  return partitions;
}

export async function readPartitionTable(esploader) {
  try {
    log("Reading partition table from 0x8000...");

    const data = await esploader.readFlash(0x8000, 0xc00);
    const uint8Data = new Uint8Array(data);

    partitions = parsePartitionTable(uint8Data);
    window.partitions = partitions;

    log(`Found ${partitions.length} partitions`);

    // Display partition table
    let html =
      '<table class="striped"><thead><tr><th>Name</th><th>Type</th><th>SubType</th><th>Offset</th><th>Size</th><th>Action</th></tr></thead><tbody>';
    partitions.forEach((p) => {
      html += `<tr>
                <td><strong>${p.label || "(none)"}</strong></td>
                <td>${p.typeName}</td>
                <td>${p.subtypeName}</td>
                <td>0x${p.offset.toString(16)}</td>
                <td>${(p.size / 1024).toFixed(0)} KB</td>
                <td>
                    <button class="button small" onclick="window.dumpPartition('${p.label}', ${p.offset}, ${p.size})">Dump</button>
                    <button class="button small primary" onclick="document.getElementById('file_${p.label}').click()">Flash</button>
                    <input type="file" id="file_${p.label}" style="display:none" onchange="window.flashPartition('${p.label}', ${p.offset}, this)">
                </td>
            </tr>`;
    });
    html += "</tbody></table>";

    document.getElementById("partitionTableContainer").innerHTML = html;

    // Validate expected partitions & Update Header Status
    const expectedPartitions = ["nvs", "otadata", "app0", "app1", "spiffs"];
    const foundNames = partitions.map((p) => p.label);
    const missing = expectedPartitions.filter(
      (name) => !foundNames.includes(name),
    );

    const statusEl = document.getElementById("partitionTableStatus");
    if (statusEl) {
      if (missing.length > 0) {
        statusEl.innerHTML = `Warning: Missing: ${missing.join(", ")}`;
        statusEl.style.color = "#dc3545";
        log(`Warning: Missing partitions: ${missing.join(", ")}`, "warning");
      } else {
        statusEl.innerHTML = `All expected partitions found`;
        statusEl.style.color = "#28a745";
      }
    }
  } catch (error) {
    log(`Failed to read partition table: ${error.message}`, "error");
  }
}

// Get active partition slot without UI updates
export async function getActivePartition(esploader) {
  const otadataOffset = 0xe000;
  const data = await esploader.readFlash(otadataOffset, 0x2000);
  const uint8Data = new Uint8Array(data);

  const entry1Seq = new DataView(uint8Data.buffer, 0, 4).getUint32(0, true);
  const entry2Seq = new DataView(uint8Data.buffer, 0x1000, 4).getUint32(
    0,
    true,
  );

  // Higher sequence number = active slot
  const activeSlot = entry1Seq > entry2Seq ? 0 : 1;
  const inactiveSlot = activeSlot === 0 ? 1 : 0;

  return {
    activeSlot,
    inactiveSlot,
    currentSeq: Math.max(entry1Seq, entry2Seq),
  };
}

export async function readOtaData(esploader) {
  try {
    log("Reading OTA data partition (0xe000)...");

    const otadataOffset = 0xe000;
    const data = await esploader.readFlash(otadataOffset, 0x2000);
    const uint8Data = new Uint8Array(data);

    // Parse and validate entry 1 (app0)
    // Structure from ESP-IDF v4.4.7 esp_flash_partitions.h:
    // typedef struct {
    //     uint32_t ota_seq;      // offset 0-3
    //     uint8_t  seq_label[20];// offset 4-23
    //     uint32_t ota_state;    // offset 24-27
    //     uint32_t crc;          // offset 28-31: CRC32 of ota_seq field only
    // } esp_ota_select_entry_t;
    const entry1Data = uint8Data.slice(0, 32);
    const entry1Seq = new DataView(
      entry1Data.buffer,
      entry1Data.byteOffset,
      4,
    ).getUint32(0, true);
    const entry1State = new DataView(
      entry1Data.buffer,
      entry1Data.byteOffset + 24,
      4,
    ).getUint32(0, true);
    const entry1CrcStored = new DataView(
      entry1Data.buffer,
      entry1Data.byteOffset + 28,
      4,
    ).getUint32(0, true);
    const entry1CrcDisplay = new DataView(
      entry1Data.buffer,
      entry1Data.byteOffset + 28,
      4,
    ).getUint32(0, false); // big-endian for display
    const entry1CrcCalc = calculateCRC32(entry1Data.slice(0, 4)); // CRC over ota_seq only (4 bytes)
    const entry1CrcValid = entry1CrcStored === entry1CrcCalc;

    // Debug logging
    log(
      `app0: seq=${entry1Seq} state=0x${entry1State.toString(16)} crc_stored=0x${entry1CrcStored.toString(16)} crc_calc=0x${entry1CrcCalc.toString(16)} bytes=${Array.from(
        entry1Data.slice(0, 4),
      )
        .map((b) => b.toString(16).padStart(2, "0"))
        .join(" ")}`,
    );

    // Helper to extract label safely (stop at 0x00 or 0xFF)
    const getLabel = (u8) => {
      const slice = u8.slice(4, 24);
      let len = 0;
      while (len < slice.length && slice[len] !== 0x00 && slice[len] !== 0xff) {
        len++;
      }
      return new TextDecoder().decode(slice.subarray(0, len)).trim();
    };

    const entry1Label = getLabel(entry1Data);

    // Parse and validate entry 2 (app1)
    const entry2Data = uint8Data.slice(0x1000, 0x1000 + 32);
    const entry2Label = getLabel(entry2Data);
    const entry2Seq = new DataView(
      entry2Data.buffer,
      entry2Data.byteOffset,
      4,
    ).getUint32(0, true);
    const entry2State = new DataView(
      entry2Data.buffer,
      entry2Data.byteOffset + 24,
      4,
    ).getUint32(0, true);
    const entry2CrcStored = new DataView(
      entry2Data.buffer,
      entry2Data.byteOffset + 28,
      4,
    ).getUint32(0, true);
    const entry2CrcDisplay = new DataView(
      entry2Data.buffer,
      entry2Data.byteOffset + 28,
      4,
    ).getUint32(0, false); // big-endian for display
    const entry2CrcCalc = calculateCRC32(entry2Data.slice(0, 4)); // CRC over ota_seq only (4 bytes)
    const entry2CrcValid = entry2CrcStored === entry2CrcCalc;

    // Debug logging
    log(
      `app1: seq=${entry2Seq} state=0x${entry2State.toString(16)} crc_stored=0x${entry2CrcStored.toString(16)} crc_calc=0x${entry2CrcCalc.toString(16)} bytes=${Array.from(
        entry2Data.slice(0, 4),
      )
        .map((b) => b.toString(16).padStart(2, "0"))
        .join(" ")}`,
    );

    // OTA state mapping
    const getOtaState = (state) => {
      if (state === 0x00000000) return "new";
      if (state === 0x00000001) return "pending_verify";
      if (state === 0x00000002) return "valid";
      if (state === 0x00000003) return "invalid";
      if (state === 0x00000004) return "aborted";
      if (state === 0xffffffff) return "pending_new";
      return `unknown(0x${state.toString(16)})`;
    };

    // Determine active partition (only if CRC valid and state is valid)
    let activeSlot = -1;
    const entry1Valid =
      entry1Seq !== 0xffffffff &&
      entry1CrcValid &&
      (getOtaState(entry1State) === "valid" ||
        getOtaState(entry1State) === "pending_new" ||
        getOtaState(entry1State) === "new");
    const entry2Valid =
      entry2Seq !== 0xffffffff &&
      entry2CrcValid &&
      (getOtaState(entry2State) === "valid" ||
        getOtaState(entry2State) === "pending_new" ||
        getOtaState(entry2State) === "new");

    if (entry1Valid && entry2Valid) {
      activeSlot = entry1Seq > entry2Seq ? 0 : 1;
    } else if (entry1Valid) {
      activeSlot = 0;
    } else if (entry2Valid) {
      activeSlot = 1;
    }

    // State and Color Logic (Must be defined BEFORE usage in HTML)
    const state1 = getOtaState(entry1State);
    const state1Color =
      state1 === "valid"
        ? "#28a745"
        : state1 === "invalid" || state1 === "aborted"
          ? "#dc3545"
          : "#6c757d";

    const state2 = getOtaState(entry2State);
    const state2Color =
      state2 === "valid"
        ? "#28a745"
        : state2 === "invalid" || state2 === "aborted"
          ? "#dc3545"
          : "#6c757d";

    let html =
      '<table class="striped"><thead><tr><th>Partition</th><th>Boot</th><th>Label</th><th>Sequence</th><th>State</th><th>CRC32</th><th>CRC Valid</th><th>Action</th></tr></thead><tbody>';

    // app0 row
    html += `<tr style="background: ${activeSlot === 0 ? "#d4edda" : ""}">
            <td><strong>app0</strong><br><small>0x10000</small></td>
            <td>${activeSlot === 0 ? '<strong style="color: #28a745;">Yes</strong>' : "No"}</td>
            <td>${entry1Label || "-"}</td>
            <td>${entry1Seq === 0xffffffff ? "-" : entry1Seq}</td>
            <td><span style="color: ${state1Color}; font-weight: 500;">${state1}</span></td>
            <td><code>${entry1CrcDisplay.toString(16).padStart(8, "0")}</code></td>
            <td><strong style="color: ${entry1CrcValid ? "#28a745" : "#dc3545"};">${entry1CrcValid ? "Yes" : "No"}</strong></td>
            <td>
              ${activeSlot === 0 ? '<button class="button success" disabled>Active</button>' : entry1Valid ? '<button class="button primary" onclick="setActivePartition(0)">Set Active</button>' : ""}
              ${entry1Valid ? `<button class="button" onclick="renamePartition(0, '${entry1Label || ""}')">Rename</button>` : ""}
            </td>
        </tr>`;

    // app1 row
    html += `<tr style="background: ${activeSlot === 1 ? "#d4edda" : ""}">
            <td><strong>app1</strong><br><small>0x650000</small></td>
            <td>${activeSlot === 1 ? '<strong style="color: #28a745;">Yes</strong>' : "No"}</td>
            <td>${entry2Label || "-"}</td>
            <td>${entry2Seq === 0xffffffff ? "-" : entry2Seq}</td>
            <td><span style="color: ${state2Color}; font-weight: 500;">${state2}</span></td>
            <td><code>${entry2CrcDisplay.toString(16).padStart(8, "0")}</code></td>
            <td><strong style="color: ${entry2CrcValid ? "#28a745" : "#dc3545"};">${entry2CrcValid ? "Yes" : "No"}</strong></td>
            <td>
              ${activeSlot === 1 ? '<button class="button success" disabled>Active</button>' : entry2Valid ? '<button class="button primary" onclick="setActivePartition(1)">Set Active</button>' : ""}
              ${entry2Valid ? `<button class="button" onclick="renamePartition(1, '${entry2Label || ""}')">Rename</button>` : ""}
            </td>
        </tr>`;

    html += "</tbody></table>";

    if (activeSlot >= 0) {
      html += `<p>Current boot partition: <code>app${activeSlot}</code></p>`;
    } else {
      html += `<p style="color: #dc3545;"><strong>Warning: No valid boot partition found!</strong></p>`;
    }

    document.getElementById("otaDataContainer").innerHTML = html;
    log(
      `Active partition: ${activeSlot >= 0 ? "app" + activeSlot : "NONE"}`,
      activeSlot >= 0 ? "success" : "error",
    );

    // Update OTA target slot selection
    const otaSlotSelect = document.getElementById("otaSlotSelect");
    if (activeSlot >= 0 && otaSlotSelect) {
      const inactiveSlot = activeSlot === 0 ? 1 : 0;
      // Assuming standard offsets for app0 and app1
      const targetOffset = inactiveSlot === 0 ? 0x10000 : 0x650000;
      otaSlotSelect.value = "0x" + targetOffset.toString(16);

      // Disable the active slot option to enforce safety
      Array.from(otaSlotSelect.options).forEach((opt) => {
        const optVal = parseInt(opt.value, 16);
        if (
          (activeSlot === 0 && optVal === 0x10000) ||
          (activeSlot === 1 && optVal === 0x650000)
        ) {
          opt.disabled = true;
          opt.text += " (Active - Do not overwrite)";
        } else {
          opt.disabled = false;
          opt.text = opt.text.replace(" (Active - Do not overwrite)", "");
        }
      });
    }
  } catch (error) {
    log(`Failed to read OTA data: ${error.message}`, "error");
  }
}

// Update OTA entry (Internal logic)
export async function updateOtaEntry(
  esploader,
  targetSlot,
  label = null,
  setActive = true,
) {
  try {
    const action = setActive ? "Setting active" : "Updating";
    log(`${action} partition app${targetSlot}...`, "info");

    const otadataOffset = 0xe000;
    // Read current sector to preserve data
    const data = await esploader.readFlash(otadataOffset, 0x2000);
    const uint8Data = new Uint8Array(data);

    // Get current sequence numbers
    const entry1Seq = new DataView(uint8Data.buffer, 0, 4).getUint32(0, true);
    const entry2Seq = new DataView(uint8Data.buffer, 0x1000, 4).getUint32(
      0,
      true,
    );

    // Calculate max sequence number
    let maxSeq = 0;
    if (entry1Seq !== 0xffffffff) maxSeq = Math.max(maxSeq, entry1Seq);
    if (entry2Seq !== 0xffffffff) maxSeq = Math.max(maxSeq, entry2Seq);

    // Determine new sequence number
    let newSeq;
    if (setActive) {
      newSeq = maxSeq + 1;
    } else {
      // Reuse existing sequence number to maintain order
      const currentSeq = targetSlot === 0 ? entry1Seq : entry2Seq;
      if (currentSeq === 0xffffffff) {
        // If target has no valid sequence, allow it to be initialized but stay inactive
        // activeSlot has maxSeq. We want newSeq < maxSeq.
        // If maxSeq is 0 (both empty), start with 1.
        newSeq = maxSeq > 0 ? maxSeq - 1 : 1;
      } else {
        newSeq = currentSeq;
      }
    }

    // Construct new 4KB sector for the TARGET slot only
    const sectorData = new Uint8Array(0x1000);
    sectorData.fill(0xff);

    // If we are reusing the sector (inactive rename), we might want to copy other fields?
    // But we are reconstructing the entry from scratch essentially.

    // Write ota_seq (offset 0-3)
    new DataView(sectorData.buffer, 0, 4).setUint32(0, newSeq, true);

    // Write seq_label (offset 4-23)
    if (label !== null) {
      const labelBytes = new TextEncoder().encode(label.substring(0, 20));
      sectorData.set(labelBytes, 4);
    } else {
      // PRESERVE EXISTING LABEL
      const oldOffset = targetSlot * 0x1000;
      sectorData.set(uint8Data.slice(oldOffset + 4, oldOffset + 24), 4);
    }

    // Write ota_state = ESP_OTA_IMG_VALID (offset 24-27)
    new DataView(sectorData.buffer, 24, 4).setUint32(0, 0x00000002, true);

    // Calculate CRC32 of ota_seq (offset 0-3 of sector)
    const crc = calculateCRC32(sectorData.slice(0, 4));
    new DataView(sectorData.buffer, 28, 4).setUint32(0, crc, true);

    const binaryString = uint8ArrayToString(sectorData);
    const targetAddress = otadataOffset + targetSlot * 0x1000;

    // Write ONLY the target sector
    await esploader.writeFlash({
      fileArray: [{ data: binaryString, address: targetAddress }],
      flashSize: "keep",
      eraseAll: false,
      compress: true,
    });

    log(
      `Success: app${targetSlot} updated (Seq: ${newSeq}). Rebooting...`,
      "success",
    );
    // Explicitly instruct user to manual reset as software reset might not suffice for OTA latching
    alert(
      "Success! Please manually RESET the device (Press Reset button, then Power button) to apply changes.",
    );
    // Always reboot to reload OTA data
  } catch (error) {
    log(`Failed to update OTA entry: ${error.message}`, "error");
    throw error;
  }
}

// UI Wrapper for Manual Action
export async function setActivePartition(esploader, targetSlot) {
  if (
    !confirm(
      `Switch boot partition to app${targetSlot}?\n\nDevice will boot from app${targetSlot} on next restart.`,
    )
  ) {
    return;
  }
  // Pass null to preserve existing label, True to set Active
  await updateOtaEntry(esploader, targetSlot, null, true);
}

// Rename Action
export async function renamePartition(esploader, targetSlot, currentLabel) {
  let label = prompt(
    `Enter new label for app${targetSlot}:`,
    currentLabel || "",
  );
  if (label === null) return;

  if (
    !confirm(
      `Rename app${targetSlot} to "${label}"?\n\nDevice will reboot to apply changes.`,
    )
  ) {
    return;
  }
  // False = Do not force active (Reuse sequence number)
  await updateOtaEntry(esploader, targetSlot, label, false);
}
