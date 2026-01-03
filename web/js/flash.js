// ========================================================================
// FLASH OPERATIONS - OTA and LittleFS
// ========================================================================

import {
  log,
  showStatus,
  updateProgress,
  hideProgress,
  uint8ArrayToString,
} from "./utils.js";
import { getEspLoader } from "./connection.js";
import { readOtaData, updateOtaEntry } from "./ota.js";

// Flash OTA
// Flash Buffer to Slot
export async function flashBufferToSlot(
  esploader,
  buffer,
  offset,
  label,
  progressBarId,
  statusId,
) {
  try {
    log(`Flashing buffer to 0x${offset.toString(16)}...`, "warning");
    if (statusId) showStatus(statusId, "Flashing...", "info");

    const binaryString = uint8ArrayToString(buffer);

    await esploader.writeFlash({
      fileArray: [{ data: binaryString, address: offset }],
      flashSize: "keep",
      eraseAll: false,
      compress: true,
      reportProgress: (idx, written, total) => {
        if (progressBarId)
          updateProgress(progressBarId, Math.round((written / total) * 100));
      },
    });

    log("Flash complete!", "success");
    if (statusId)
      showStatus(
        statusId,
        "Flash complete! Updating boot partition...",
        "info",
      );

    // Automatically set as active
    const targetSlot = offset === 0x10000 ? 0 : 1;
    await updateOtaEntry(esploader, targetSlot, label, true);

    log(
      "Flash & activation complete! Please press RESET then POWER button to reboot.",
      "success",
    );
    if (statusId)
      showStatus(
        statusId,
        "Update complete! Press RESET then POWER button.",
        "success",
      );

    // Soft reset
    try {
      await esploader.hardReset();
      log("Soft reset command sent (if supported).", "info");
    } catch (e) {
      log(
        "Auto-reset failed. Please press the Reset button manually.",
        "warning",
      );
    }

    if (progressBarId) hideProgress(progressBarId);

    // Refresh OTA data display
    await readOtaData(esploader);
  } catch (error) {
    log(`Flash failed: ${error.message}`, "error");
    if (statusId)
      showStatus(statusId, `Flash failed: ${error.message}`, "error");
    if (progressBarId) hideProgress(progressBarId);
    throw error;
  }
}

// Flash OTA
export async function flashOta() {
  const fileInput = document.getElementById("otaFile");
  const offset = parseInt(document.getElementById("otaSlotSelect").value);

  if (!fileInput.files.length) {
    showStatus("otaStatus", "Please select an OTA file", "error");
    return;
  }

  const esploader = getEspLoader();
  if (!esploader) {
    showStatus("otaStatus", "Please connect to device first", "error");
    return;
  }

  try {
    const file = fileInput.files[0];
    const arrayBuffer = await file.arrayBuffer();
    const data = new Uint8Array(arrayBuffer);

    const labelInput = document.getElementById("otaLabel");
    const label = labelInput ? labelInput.value : "";

    await flashBufferToSlot(
      esploader,
      data,
      offset,
      label,
      "otaProgressBar",
      "otaStatus",
    );
  } catch (error) {
    // Error handled in flashBufferToSlot but re-caught here for safety or specific OTA UI logic if needed
  }
}

// Flash Generic Partition
export async function flashPartition(name, offset, inputElement) {
  if (!inputElement.files.length) return;

  const esploader = getEspLoader();
  if (!esploader) {
    alert("Please connect to device first");
    return;
  }

  const file = inputElement.files[0];
  if (
    !confirm(
      `Are you sure you want to FLASH partition '${name}' with '${file.name}'?\nThis will overwrite existing data at 0x${offset.toString(16)}.`,
    )
  ) {
    inputElement.value = ""; // Reset
    return;
  }

  try {
    log(
      `Flashing partition '${name}' (0x${offset.toString(16)})...`,
      "warning",
    );

    // Reuse backup/device info status elements if possible, or fallback to log
    // Actually, since this is triggered from the table, let's use the backup status/progress if visible,
    // or just use a modal? No, let's assume backupProgressBar (which is in Device Info) is usable.
    const progressBarId = "backupProgressBar";
    const statusId = "backupStatus";

    const statusEl = document.getElementById(statusId);
    if (statusEl) statusEl.innerText = `Flashing ${name}...`;

    const arrayBuffer = await file.arrayBuffer();
    const data = new Uint8Array(arrayBuffer);

    // Convert to binary string safely
    const binaryString = uint8ArrayToString(data);

    await esploader.writeFlash({
      fileArray: [{ data: binaryString, address: offset }],
      flashSize: "keep",
      eraseAll: false,
      compress: true,
      reportProgress: (idx, written, total) => {
        updateProgress(progressBarId, Math.round((written / total) * 100));
      },
    });

    log(`Partition '${name}' flashed successfully!`, "success");
    if (statusEl) statusEl.innerText = `${name} Flashed! Reset device.`;
    hideProgress(progressBarId);
  } catch (error) {
    log(`Flash failed: ${error.message}`, "error");
    alert(`Flash failed: ${error.message}`);
    hideProgress("backupProgressBar");
  } finally {
    inputElement.value = ""; // Reset input to allow re-uploading same file
  }
}
