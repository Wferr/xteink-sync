// ========================================================================
// MAIN INITIALIZATION
// ========================================================================

import { log } from "./utils.js";
import { connect, disconnect } from "./connection.js";
import { setActivePartition } from "./ota.js";
import {
  initPatchUI,
  downloadKnownFirmware,
  uploadKnownFirmware,
  patchAndDownload,
  resetDownloadedFirmware,
  downloadOriginal,
} from "./patching.js";
import { backupFullFlash, dumpPartition, restoreFullFlash } from "./backup.js";
import { flashOta, flashPartition } from "./flash.js";
import { readNvsPartition } from "./nvs.js";

// Expose for usage in other modules (and inline HTML onclicks)
window.dumpPartition = dumpPartition;
window.flashPartition = flashPartition; // New

import {
  FIRMWARE_CONFIG,
  FIRMWARE_VERSIONS,
  loadFirmwareConfig,
  loadFirmwareVersions,
} from "./config.js";
import { updateFirmwareInfo } from "./ui-helpers.js";

// Import esptool-js as module
import {
  ESPLoader,
  Transport,
} from "https://unpkg.com/esptool-js@0.5.7/bundle.js";

// Make functions available globally for onclick handlers
window.setActivePartition = async (slot) => {
  const esploader = window.esploader;
  if (esploader) {
    await setActivePartition(esploader, slot);
  }
};

window.esploader = null; // Expose for other modules

// Initialize on page load
document.addEventListener("DOMContentLoaded", async () => {
  // Load firmware versions list first
  try {
    await loadFirmwareVersions();

    // Populate version dropdown
    const versionSelect = document.getElementById("firmwareVersionSelect");
    if (versionSelect && FIRMWARE_VERSIONS) {
      versionSelect.innerHTML = "";
      FIRMWARE_VERSIONS.versions.forEach((version) => {
        const option = document.createElement("option");
        option.value = version.id;
        option.textContent = `${version.name} - ${version.description}${version.default ? " (Default)" : ""}`;
        option.selected = version.default;
        versionSelect.appendChild(option);
      });
    }
  } catch (error) {
    log(`Failed to load firmware versions: ${error.message}`, "error");
  }

  // Load default firmware config
  try {
    const defaultVersion =
      FIRMWARE_VERSIONS?.versions.find((v) => v.default)?.id || "v3.1.5";
    await loadFirmwareConfig(defaultVersion);
    updateFirmwareInfo();
    log(`Firmware config loaded: ${FIRMWARE_CONFIG.version}`, "success");
  } catch (error) {
    log(`Failed to load firmware config: ${error.message}`, "error");
    log("Config load error: " + error.message, "error");
    return;
  }

  // Initialize patch UI
  initPatchUI();

  // Wire up firmware version selector
  const versionSelect = document.getElementById("firmwareVersionSelect");
  if (versionSelect) {
    versionSelect.addEventListener("change", async (e) => {
      try {
        await loadFirmwareConfig(e.target.value);
        updateFirmwareInfo();
        initPatchUI();
        resetDownloadedFirmware();
        log(`Switched to ${FIRMWARE_CONFIG.version}`, "success");
      } catch (error) {
        log(`Failed to load firmware: ${error.message}`, "error");
      }
    });
  }

  // Wire up connection toggle button
  const connectBtn = document.getElementById("connectBtn");
  if (connectBtn) {
    connectBtn.addEventListener("click", async () => {
      const isConnected = connectBtn.getAttribute("data-connected") === "true";
      if (isConnected) {
        await disconnect();
        window.esploader = null;
      } else {
        const newEsploader = await connect(ESPLoader, Transport);
        if (newEsploader) {
          window.esploader = newEsploader;
        }
      }
    });
  }

  // Wire up firmware patching buttons
  const downloadBtn = document.getElementById("downloadFirmwareBtn");
  if (downloadBtn) {
    downloadBtn.addEventListener("click", () => {
      downloadKnownFirmware();
    });
  }

  const uploadInput = document.getElementById("uploadFirmwareFile");
  if (uploadInput) {
    uploadInput.addEventListener("change", (e) => {
      const file = e.target.files[0];
      if (file) {
        uploadKnownFirmware(file);
      }
    });
  }

  // Link custom button trigger
  const btnUpload = document.getElementById("btnUploadFirmware");
  if (btnUpload) {
    btnUpload.addEventListener("click", () => uploadInput.click());
  }

  const originalBtn = document.getElementById("downloadOriginalBtn");
  if (originalBtn) {
    originalBtn.addEventListener("click", downloadOriginal);
  }

  const patchDownloadBtn = document.getElementById("patchDownloadBtn");
  if (patchDownloadBtn) {
    patchDownloadBtn.addEventListener("click", patchAndDownload);
  }

  /* patchFlashBtn logic removed
  const patchFlashBtn = document.getElementById("patchFlashBtn");
  if (patchFlashBtn) {
    patchFlashBtn.addEventListener("click", patchAndFlash);
  }
  */

  // Wire up backup buttons
  const backupBtn = document.getElementById("backupBtn");
  if (backupBtn) {
    backupBtn.addEventListener("click", backupFullFlash);
  }
  const restoreInput = document.getElementById("restoreInput");
  if (restoreInput) {
    restoreInput.addEventListener("change", restoreFullFlash);
  }

  // Wire up OTA flash buttons
  const otaFile = document.getElementById("otaFile");
  const btnUploadOta = document.getElementById("btnUploadOta");
  if (otaFile && btnUploadOta) {
    btnUploadOta.addEventListener("click", () => otaFile.click());
  }

  // Handle OTA file selection (UI update & validation)
  if (otaFile) {
    otaFile.addEventListener("change", (e) => {
      const file = e.target.files[0];
      const nameDisplay = document.getElementById("otaFileName");

      if (!file) {
        if (nameDisplay) nameDisplay.textContent = "None";
        return;
      }

      let validationMsg = "";
      let valid = true;

      // Check file size against selected partition
      const slotSelect = document.getElementById("otaSlotSelect");
      if (slotSelect && window.partitions) {
        // Parse target address from hex string value
        const targetOffset = parseInt(slotSelect.value, 16);
        // Find partition by offset
        const targetPartition = window.partitions.find(p => p.offset === targetOffset);

        if (targetPartition) {
          if (file.size > targetPartition.size) {
            valid = false;
            validationMsg = ` <span style="color:red; font-weight:bold;">(Error: File size ${(file.size / 1024).toFixed(1)}KB exceeds partition size ${(targetPartition.size / 1024).toFixed(1)}KB)</span>`;
          } else {
            validationMsg = ` <span style="color:green;">(${(file.size / 1024).toFixed(1)}KB / ${(targetPartition.size / 1024).toFixed(1)}KB)</span>`;
          }
        }
      }

      if (nameDisplay) {
        nameDisplay.innerHTML = `<strong>${file.name}</strong>${validationMsg}`;

        // Disable flash button if invalid
        const flashBtn = document.getElementById("flashOtaBtn");
        if (flashBtn) flashBtn.disabled = !valid;
      }
    });
  }

  const flashOtaBtn = document.getElementById("flashOtaBtn");
  if (flashOtaBtn) {
    flashOtaBtn.addEventListener("click", flashOta);
  }

  // Wire up NVS button
  const readNvsBtn = document.getElementById("readNvsBtn");
  if (readNvsBtn) {
    readNvsBtn.addEventListener("click", () => {
      if (window.esploader) {
        readNvsPartition(window.esploader);
      } else {
        alert("Please connect to a device first.");
      }
    });
  }

  log("Web Flasher ready. Select baud rate and connect...", "success");
});
