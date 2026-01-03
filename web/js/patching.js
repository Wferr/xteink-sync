import { log, showStatus, updateProgress, hideProgress } from "./utils.js";
import { FIRMWARE_CONFIG } from "./config.js";
import { flashBufferToSlot } from "./flash.js";
import { getActivePartition } from "./ota.js";
import { getEspLoader } from "./connection.js";

let downloadedFirmware = null;

function updatePatchButtons() {
  // Check if all required AND enabled patches have values
  const allRequired = FIRMWARE_CONFIG.patches
    .filter((p, i) => {
      const checkbox = document.getElementById(`patchEnable${i}`);
      return p.required && checkbox && checkbox.checked;
    })
    .every((p, i) => {
      const input = document.getElementById(`patch${i}`);
      return input && input.value.trim();
    });

  const hasDownloaded = downloadedFirmware !== null;
  const isConnected = !!getEspLoader(); // Check connection status for Flash button

  const downloadBtn = document.getElementById("patchDownloadBtn");
  const flashBtn = document.getElementById("patchFlashBtn");
  const originalBtn = document.getElementById("downloadOriginalBtn");

  if (downloadBtn) downloadBtn.disabled = !allRequired || !hasDownloaded;
  if (originalBtn) originalBtn.disabled = !hasDownloaded;

  // Enable Flash button only if connected AND ready
  if (flashBtn)
    flashBtn.disabled = !allRequired || !hasDownloaded || !isConnected;
}

// Patch and Flash
export async function patchAndFlash() {
  try {
    const esploader = getEspLoader();
    if (!esploader) {
      showStatus("patchStatus", "Please connect to device first", "error");
      return;
    }

    showStatus("patchStatus", "Preparing firmware...", "info");
    updateProgress("patchProgressBar", 20);

    const patched = await applyPatches(downloadedFirmware);

    // Determine basic version info
    // Clean up version string: "V3.1.5" -> "v3.1.5", "V3.1.1-EN" -> "v3.1.1-en"
    let baseLabel = (FIRMWARE_CONFIG.version || "unknown").toLowerCase();

    // Try to detect Lang from filename if not in version
    if (
      !baseLabel.includes("en") &&
      !baseLabel.includes("ch") &&
      !baseLabel.includes("cn")
    ) {
      if (
        FIRMWARE_CONFIG.filename.includes("CH") ||
        FIRMWARE_CONFIG.filename.includes("CN")
      ) {
        baseLabel += "-ch";
      } else if (FIRMWARE_CONFIG.filename.includes("EN")) {
        baseLabel += "-en";
      }
    }

    // Determine Mod suffix
    const activePatches = FIRMWARE_CONFIG.patches.filter((p, i) => {
      const checkbox = document.getElementById(`patchEnable${i}`);
      return checkbox && checkbox.checked;
    });

    let modSuffix = "";
    if (activePatches.length > 0) {
      modSuffix = "-mod";
    }

    // Construct Label (Max 20 chars)
    // format: version-lang-mod
    // e.g. v3.1.5-ch-mod
    let label = `${baseLabel}${modSuffix}`;

    // Truncate if too long (prioritize keeping mod suffix)
    if (label.length > 20) {
      if (modSuffix) {
        const allowedBase = 20 - modSuffix.length;
        label = baseLabel.substring(0, allowedBase) + modSuffix;
      } else {
        label = label.substring(0, 20);
      }
    }

    log(`Generated boot label: ${label}`, "info");

    // Determine Inactive Slot
    const { inactiveSlot } = await getActivePartition(esploader);
    const targetOffset = inactiveSlot === 0 ? 0x10000 : 0x650000;

    log(
      `Targeting inactive slot: app${inactiveSlot} (0x${targetOffset.toString(16)})`,
      "info",
    );

    await flashBufferToSlot(
      esploader,
      patched,
      targetOffset,
      label,
      "patchProgressBar",
      "patchStatus",
    );
  } catch (error) {
    log(`Patch & Flash failed: ${error.message}`, "error");
    showStatus("patchStatus", `Failed: ${error.message}`, "error");
    hideProgress("patchProgressBar");
  }
}

// ESP32 checksum recalculation
async function fixESP32Checksums(content) {
  if (content.length < 64) return content;

  const segmentsCount = content[1];
  let pos = 24;
  let checksum = 0xef;

  for (let i = 0; i < segmentsCount; i++) {
    if (pos + 8 > content.length) break;

    const length = new DataView(
      content.buffer,
      content.byteOffset + pos + 4,
      4,
    ).getUint32(0, true);
    pos += 8;

    for (let j = 0; j < length && pos + j < content.length; j++) {
      checksum ^= content[pos + j];
    }

    pos += length;
  }

  const checksumPos = content.length - 33;
  if (checksumPos > 0) {
    log(
      `Checksum: 0x${content[checksumPos].toString(16)} -> 0x${checksum.toString(16)}`,
    );
    content[checksumPos] = checksum;
  }

  const dataToHash = content.slice(0, -32);

  const hash = await crypto.subtle.digest("SHA-256", dataToHash);
  const hashArray = new Uint8Array(hash);
  log(
    `SHA256: ${Array.from(hashArray.slice(0, 4))
      .map((b) => b.toString(16).padStart(2, "0"))
      .join("")}...`,
  );
  content.set(hashArray, content.length - 32);
  return content;
}

// Initialize patch input UI
export function initPatchUI() {
  const container = document.getElementById("patchInputs");
  if (!container) {
    log("Error: patchInputs container not found", "error");
    return;
  }

  if (!FIRMWARE_CONFIG || !FIRMWARE_CONFIG.patches) {
    log("Error: FIRMWARE_CONFIG or patches not loaded!", "error");
    return;
  }

  let html = "";

  FIRMWARE_CONFIG.patches.forEach((patch, index) => {
    const required = patch.required ? " *" : "";
    const checked = patch.enabled !== false ? "checked" : "";
    const disabled = patch.enabled !== false ? "" : "disabled";

    html += `
            <p>
                <strong>${patch.name}${required}</strong> <span class="text-grey" style="font-weight: normal; margin-left: 0.5rem;">${patch.description}</span>
            </p>
            <p class="grouped">
                <label>
                    <input type="checkbox" id="patchEnable${index}" ${checked}>
                    Enable
                </label>
                <input type="text" 
                       id="patch${index}" 
                       data-patch-name="${patch.name}"
                       placeholder="${patch.find}"
                       maxlength="${patch.maxLength}" 
                       ${disabled}
                       style="width: 100%;">
            </p>
            <p style="margin-top: -10px;">
                <small class="text-grey">
                    Replaces: <code>${patch.find}</code> (max ${patch.maxLength} chars)
                </small>
            </p>
            <hr style="margin: 0.5rem 0;">
        `;
  });

  container.innerHTML = html;

  // Add change listeners for checkboxes
  FIRMWARE_CONFIG.patches.forEach((patch, index) => {
    const checkbox = document.getElementById(`patchEnable${index}`);
    const input = document.getElementById(`patch${index}`);

    if (checkbox) {
      checkbox.addEventListener("change", (e) => {
        // Enable/disable the text input
        if (input) {
          input.disabled = !e.target.checked;
          if (!e.target.checked) {
            input.value = ""; // Clear value when disabled
          }
        }
        updatePatchButtons();
      });
    }

    if (input) {
      input.addEventListener("input", updatePatchButtons);
    }
  });
}

// Reset downloaded firmware
export function resetDownloadedFirmware() {
  downloadedFirmware = null;
  updatePatchButtons();
}

// Download known firmware
export async function downloadKnownFirmware() {
  try {
    log(`Downloading ${FIRMWARE_CONFIG.filename}...`, "info");
    showStatus("patchStatus", "Downloading firmware...", "info");
    updateProgress("patchProgressBar", 0);

    const response = await fetch(FIRMWARE_CONFIG.url);
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const contentLength = response.headers.get("content-length");
    const total = parseInt(contentLength, 10);
    let loaded = 0;
    let lastLogTime = Date.now();

    const reader = response.body.getReader();
    const chunks = [];

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      chunks.push(value);
      loaded += value.length;

      if (total) {
        const percent = Math.round((loaded / total) * 100);
        updateProgress("patchProgressBar", percent);

        // Only log every 1 second to reduce spam
        const now = Date.now();
        if (now - lastLogTime >= 1000) {
          log(
            `Downloaded ${(loaded / 1024 / 1024).toFixed(1)} MB / ${(total / 1024 / 1024).toFixed(1)} MB (${percent}%)`,
          );
          lastLogTime = now;
        }
      }
    }

    // Combine chunks
    const arrayBuffer = new Uint8Array(loaded);
    let position = 0;
    for (const chunk of chunks) {
      arrayBuffer.set(chunk, position);
      position += chunk.length;
    }

    downloadedFirmware = arrayBuffer;

    // Verify checksum
    updateProgress("patchProgressBar", 100);
    log("Verifying checksum...", "info");
    const wordArray = CryptoJS.lib.WordArray.create(downloadedFirmware);
    const sha256 = CryptoJS.SHA256(wordArray).toString();

    if (sha256 !== FIRMWARE_CONFIG.checksums.sha256) {
      throw new Error("SHA256 checksum mismatch! File may be corrupted.");
    }

    log(
      `Downloaded ${FIRMWARE_CONFIG.filename} (${downloadedFirmware.length} bytes)`,
      "success",
    );
    log(`SHA256 verified: ${sha256}`, "success");

    showStatus(
      "patchStatus",
      "Firmware downloaded and verified. Ready to patch.",
      "success",
    );

    // Hide progress bar after 2 seconds
    setTimeout(() => {
      hideProgress("patchProgressBar");
    }, 2000);
    updatePatchButtons();
  } catch (error) {
    log(`Download failed: ${error.message}`, "error");
    showStatus("patchStatus", `Download failed: ${error.message}`, "error");
    hideProgress("patchProgressBar");

    downloadedFirmware = null;
    updatePatchButtons();
  }
}

// Upload pre-downloaded firmware
export async function uploadKnownFirmware(file) {
  try {
    log(`Uploading ${file.name}...`, "warning");
    showStatus("patchStatus", "Loading firmware...", "info");

    const arrayBuffer = await file.arrayBuffer();
    const firmware = new Uint8Array(arrayBuffer);

    // Verify it's the right version by checking SHA256
    const wordArray = CryptoJS.lib.WordArray.create(firmware);
    const sha256 = CryptoJS.SHA256(wordArray).toString();

    if (sha256 !== FIRMWARE_CONFIG.checksums.sha256) {
      throw new Error(
        `Wrong firmware version! Expected V3.1.5.\nSHA256: ${sha256}`,
      );
    }

    downloadedFirmware = firmware;
    log(`Loaded ${file.name} (${firmware.length} bytes)`, "success");
    log(`SHA256 verified: ${sha256}`, "success");
    showStatus(
      "patchStatus",
      "Firmware loaded and verified. Ready to patch.",
      "success",
    );

    updatePatchButtons();
  } catch (error) {
    log(`Upload failed: ${error.message}`, "error");
    showStatus("patchStatus", `Upload failed: ${error.message}`, "error");
    downloadedFirmware = null;
    updatePatchButtons();
  }
}

// Apply patches to firmware
async function applyPatches(firmware) {
  let patched = new Uint8Array(firmware);
  let patchCount = 0;

  for (let i = 0; i < FIRMWARE_CONFIG.patches.length; i++) {
    const patch = FIRMWARE_CONFIG.patches[i];
    const checkbox = document.getElementById(`patchEnable${i}`);
    const isEnabled = checkbox ? checkbox.checked : true;

    // Skip if patch is disabled
    if (!isEnabled) {
      log(`Skipping disabled patch: ${patch.name}`, "info");
      continue;
    }

    const inputValue = document.getElementById(`patch${i}`).value.trim();

    if (!inputValue) {
      if (patch.required) {
        throw new Error(`${patch.name} is required`);
      }
      log(`Skipping empty patch: ${patch.name}`, "info");
      continue;
    }

    // Support multiple targets per patch input (e.g. different URLs for same IP)
    const targets = patch.replacements || [patch];

    for (const target of targets) {
      let newValue = inputValue;

      // Apply template if exists (e.g. "http://{value}:5000/...")
      if (target.template) {
        newValue = target.template.replace("{value}", inputValue);
      }

      log(`Applying patch: ${target.find} -> ${newValue}`);

      const findBytes = new TextEncoder().encode(target.find);
      const replaceBytes = new TextEncoder().encode(newValue);

      // Use target.maxLength or fallback to findBytes.length (strict replacement)
      const maxLen = target.maxLength || findBytes.length;

      if (replaceBytes.length > maxLen) {
        throw new Error(
          `Replacement too long (max ${maxLen} chars, got ${replaceBytes.length})`,
        );
      }

      // Pad with null bytes to FILL the entire maxLen buffer
      // This ensures we overwrite slack space correctly if expanding,
      // or zero out old data if shrinking.
      const paddedReplace = new Uint8Array(maxLen);
      paddedReplace.fill(0);
      paddedReplace.set(replaceBytes);

      let count = 0;
      // Scan for findBytes
      for (
        let offset = 0;
        offset <= patched.length - findBytes.length;
        offset++
      ) {
        let match = true;
        for (let j = 0; j < findBytes.length; j++) {
          if (patched[offset + j] !== findBytes[j]) {
            match = false;
            break;
          }
        }
        if (match) {
          // Write the FULL padded buffer (potentially overwriting slack)
          patched.set(paddedReplace, offset);
          count++;
          // Skip ahead by findBytes length (or maxLen? usually findBytes is safer to avoid skipping overlap, but we just overwrote maxLen...)
          // If we overwrote maxLen, we should skip maxLen to avoid re-matching inside our own write?
          // But if findBytes was small and we wrote huge slack, we might want to skip maxLen.
          // Python script skips `total_buffer_size`.
          offset += maxLen - 1;
        }
      }
      log(
        `Success: Replaced ${count} occurrence(s) of ${target.find}`,
        "success",
      );
    }
    patchCount++;
  }

  log(`Applied ${patchCount} patch(es) total`, "success");

  // Recalculate ESP32 checksums
  log("Recalculating checksums...");
  patched = await fixESP32Checksums(patched);

  return patched;
}

// Patch and download
export async function patchAndDownload() {
  try {
    showStatus("patchStatus", "Patching firmware...", "info");
    updateProgress("patchProgressBar", 50);

    const patched = await applyPatches(downloadedFirmware);

    // Generate filename from patches
    let filenameSuffix = "";
    const patchInputs = document.querySelectorAll("#patchInputs input");
    patchInputs.forEach((input) => {
      if (input.value) {
        // Sanitize value for filename
        const safeValue = input.value.replace(/[^a-zA-Z0-9-._]/g, "_");
        // Get patch name from label or ID if possible, here using clean approach:
        // Assuming current structure, we might iterate over FIRMWARE_CONFIG.patches differently
        // But simply appending values is a good start as per request
        const patchName = input.getAttribute("data-patch-name") || "patch";
        filenameSuffix += `-${patchName}-${safeValue}`;
      }
    });

    const blob = new Blob([patched], { type: "application/octet-stream" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${FIRMWARE_CONFIG.filename.replace(".bin", "")}${filenameSuffix}.bin`;
    a.click();
    URL.revokeObjectURL(url);

    updateProgress("patchProgressBar", 100);
    log(`Downloaded: ${a.download}`, "success");
    showStatus(
      "patchStatus",
      `Patched firmware saved: ${a.download}`,
      "success",
    );

    setTimeout(() => {
      hideProgress("patchProgressBar");
    }, 2000);
  } catch (error) {
    log(`Patch failed: ${error.message}`, "error");
    showStatus("patchStatus", `Patch failed: ${error.message}`, "error");
    hideProgress("patchProgressBar");
  }
}

// Download original unpatched firmware
export function downloadOriginal() {
  if (!downloadedFirmware) return;

  const blob = new Blob([downloadedFirmware], {
    type: "application/octet-stream",
  });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = FIRMWARE_CONFIG.filename || "firmware.bin";
  a.click();
  URL.revokeObjectURL(url);

  log(`Downloaded original: ${a.download}`, "success");
}
