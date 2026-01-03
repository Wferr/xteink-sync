// ========================================================================
// UI HELPER FUNCTIONS
// ========================================================================

import { FIRMWARE_CONFIG } from "./config.js";

// Update firmware info display
export function updateFirmwareInfo() {
  const infoEl = document.getElementById("firmwareInfo");
  if (infoEl && FIRMWARE_CONFIG) {
    const sizeMB = (FIRMWARE_CONFIG.size / 1024 / 1024).toFixed(1);
    infoEl.innerHTML = `<strong>${FIRMWARE_CONFIG.filename}</strong> (${sizeMB} MB)`;
  }

  // Update button text
  const downloadBtn = document.getElementById("downloadFirmwareBtn");
  if (downloadBtn && FIRMWARE_CONFIG) {
    downloadBtn.textContent = `Load Firmware`;
  }
}
