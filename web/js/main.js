// ========================================================================
// MAIN INITIALIZATION
// ========================================================================

import { log, showStatus, updateProgress, hideProgress } from "./utils.js";
import { connect, disconnect, getEspLoader } from "./connection.js";
import {
  setActivePartition,
  getActivePartition,
  renamePartition,
} from "./ota.js";
import {
  initPatchUI,
  downloadKnownFirmware,
  uploadKnownFirmware,
  patchAndDownload,
  patchAndFlash,
  resetDownloadedFirmware,
  downloadOriginal,
} from "./patching.js";
import { backupFullFlash, dumpPartition, restoreFullFlash } from "./backup.js";
import { flashOta, flashPartition, flashBufferToSlot } from "./flash.js";
import { readNvsPartition } from "./nvs.js";

// ========================================================================
// CROSSPOINT LOGIC
// ========================================================================
async function fetchCrossPointInfo() {
  const link = document.getElementById("cpReleaseLink");
  if (!link) return;

  try {
    const resp = await fetch(
      "https://api.github.com/repos/daveallie/crosspoint-reader/releases/latest",
    );
    if (!resp.ok) throw new Error("Fetch failed");
    const data = await resp.json();
    const version = data.tag_name || "Unknown";

    link.textContent = version;
    link.href = data.html_url || "#";

    const btn = document.getElementById("installCrossPointBtn");
    if (btn) btn.textContent = `Download & Install ${version}`;
  } catch (e) {
    link.textContent = "Error";
    console.error(`Failed to fetch CrossPoint info: ${e.message}`);
  }
}

async function downloadCrossPoint() {
  const btn = document.getElementById("downloadCrossPointBtn");
  const originalText = btn ? btn.textContent : "";

  try {
    if (btn) {
      btn.textContent = "Fetching URL...";
      btn.disabled = true;
    }

    // Fetch release info
    const releaseUrl =
      "https://api.github.com/repos/daveallie/crosspoint-reader/releases/latest";
    const resp = await fetch(releaseUrl);
    if (!resp.ok) throw new Error(`GitHub API Error: ${resp.status}`);

    const releaseData = await resp.json();
    const version = releaseData.tag_name || "latest";

    // Find asset
    const firmwareAsset = releaseData.assets.find((a) =>
      a.name.endsWith("firmware.bin"),
    );
    if (!firmwareAsset)
      throw new Error("No firmware.bin found in latest release");

    log(`Found CrossPoint ${version}: ${firmwareAsset.name}`, "success");

    // Manual Download
    const downloadUrl = firmwareAsset.browser_download_url;
    window.open(downloadUrl, "_blank");
  } catch (error) {
    log(`Download failed: ${error.message}`, "error");
    alert(`Download failed: ${error.message}`);
  } finally {
    if (btn) {
      btn.textContent = originalText;
      btn.disabled = false;
    }
  }
}

// Wire up firmware patching buttons

const patchFlashBtn = document.getElementById("patchFlashBtn");
if (patchFlashBtn) {
  patchFlashBtn.addEventListener("click", async () => {
    await patchAndFlash();
    await disconnect();
  });
}

// Wire up CrossPoint buttons
const downloadCpBtn = document.getElementById("downloadCrossPointBtn");
if (downloadCpBtn) {
  downloadCpBtn.addEventListener("click", downloadCrossPoint);
}

// Expose for usage in other modules (and inline HTML onclicks)
window.dumpPartition = dumpPartition;
window.flashPartition = flashPartition;

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
    await disconnect();
  }
};

window.renamePartition = async (slot, label) => {
  const esploader = window.esploader;
  if (esploader) {
    await renamePartition(esploader, slot, label);
    await disconnect();
  }
};

window.esploader = null;

// ========================================================================
// EVENT LISTENERS & INITIALIZATION
// ========================================================================
document.addEventListener("DOMContentLoaded", async () => {
  // Load firmware versions list first
  try {
    // Start fetching CrossPoint info in parallel/background
    fetchCrossPointInfo();

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
        const targetPartition = window.partitions.find(
          (p) => p.offset === targetOffset,
        );

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
    flashOtaBtn.addEventListener("click", async () => {
      await flashOta();
      await disconnect();
    });
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

  // Wire up QR Parser
  const btnParseQr = document.getElementById("btnParseQr");
  const qrInput = document.getElementById("qrHexInput");
  const qrResults = document.getElementById("qrResults");
  const qrResultsPre = document.getElementById("qrResultsPre");

  if (btnParseQr) {
    btnParseQr.addEventListener("click", () => {
      const hex = qrInput.value.trim();
      if (!hex) {
        alert("Please enter a hex string");
        return;
      }

      // Dynamic import if not top-level, or just use imported function
      // verify we imported it at top level? No, let's do dynamic import or update imports
      import("./qr-utils.js")
        .then((module) => {
          const result = module.parseQrCode(hex);
          if (qrResults && qrResultsPre) {
            qrResults.classList.remove("is-hidden");
            if (result.success) {
              qrResultsPre.textContent = JSON.stringify(result, null, 2);
              qrResultsPre.style.color = "inherit";
              log("QR Parsed Successfully", "success");
            } else {
              qrResultsPre.textContent = `Error: ${result.error}`;
              qrResultsPre.style.color = "red";
              log(`QR Parse Error: ${result.error}`, "error");
            }
          }
        })
        .catch((err) => {
          log(`Failed to load qr-utils: ${err.message}`, "error");
        });
    });
  }

  log("Web Flasher ready. Select baud rate and connect...", "success");
});
