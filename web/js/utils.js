// ========================================================================
// UTILITY FUNCTIONS
// ========================================================================

export function log(message, type = "info") {
  const logDiv = document.getElementById("consoleLog");
  const timestamp = new Date().toLocaleTimeString();

  const span = document.createElement("span");
  span.textContent = `[${timestamp}] ${message}\n`;

  if (type === "error") {
    span.style.color = "#dc3545";
    console.error(`[${timestamp}] ${message}`);
  } else if (type === "success") {
    span.style.color = "#28a745";
    console.log(`[${timestamp}] ${message}`);
  } else if (type === "warning") {
    span.style.color = "#ffc107";
    console.warn(`[${timestamp}] ${message}`);
  } else {
    console.log(`[${timestamp}] ${message}`);
  }

  logDiv.appendChild(span);
  logDiv.scrollTop = logDiv.scrollHeight;
}

export function showStatus(elementId, message, type) {
  const statusDiv = document.getElementById(elementId);
  statusDiv.className =
    type === "error" ? "text-error" : type === "success" ? "text-success" : "";
  statusDiv.textContent = message;
}

export function updateProgress(progressBarId, percent) {
  const progressBar = document.getElementById(progressBarId);
  if (progressBar) {
    progressBar.classList.remove("is-hidden");
    progressBar.value = percent;
    // progressBar.textContent = `${percent}%`; // Fallback text
  }
}

export function hideProgress(progressBarId) {
  const progressBar = document.getElementById(progressBarId);
  if (progressBar) {
    progressBar.classList.add("is-hidden");
    progressBar.value = 0;
  }
}

// CRC32 calculation matching ESP-IDF bootloader
// Equivalent to: crc32(ota_seq_bytes, 0) from 'crc/crc32' library
// Key difference: starts with CRC = 0, not 0xFFFFFFFF
export function calculateCRC32(data) {
  // Build CRC table (polynomial 0xEDB88320)
  const table = new Uint32Array(256);
  for (let i = 0; i < 256; i++) {
    let c = i;
    for (let j = 0; j < 8; j++) {
      c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    }
    table[i] = c;
  }

  // Calculate CRC starting with 0 (NOT 0xFFFFFFFF!)
  let crc = 0;
  for (let i = 0; i < data.length; i++) {
    crc = (crc >>> 8) ^ table[(crc ^ data[i]) & 0xff];
  }

  // Final XOR with 0xFFFFFFFF
  return (crc ^ 0xffffffff) >>> 0;
}

/**
 * Helper to convert Uint8Array to binary string in chunks to avoid stack overflow
 * @param {Uint8Array} u8Array
 * @returns {string}
 */
export function uint8ArrayToString(u8Array) {
  let binStr = "";
  // Use a chunk size that is safe regardless of browser (e.g. 32KB)
  const chunkSize = 0x8000;
  for (let i = 0; i < u8Array.length; i += chunkSize) {
    binStr += String.fromCharCode(...u8Array.subarray(i, i + chunkSize));
  }
  return binStr;
}
