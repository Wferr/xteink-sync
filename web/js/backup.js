// ========================================================================
// BACKUP AND RESTORE OPERATIONS
// ========================================================================

import {
  log,
  showStatus,
  updateProgress,
  hideProgress,
  uint8ArrayToString,
} from "./utils.js";
import { getEspLoader } from "./connection.js";

// Full backup
export async function backupFullFlash() {
  const esploader = getEspLoader();
  if (!esploader) {
    showStatus("backupStatus", "Please connect to device first", "error");
    return;
  }

  try {
    log("Creating full flash backup (16 MB)...", "warning");
    showStatus("backupStatus", "Backing up flash...", "info");

    const flashSize = 16 * 1024 * 1024;
    const chunkSize = 4096;
    const chunks = [];

    for (let offset = 0; offset < flashSize; offset += chunkSize) {
      updateProgress(
        "backupProgressBar",
        Math.round((offset / flashSize) * 100),
      );
      const data = await esploader.readFlash(offset, chunkSize);
      chunks.push(new Uint8Array(data));

      if (offset % (256 * 1024) === 0) {
        log(`Read ${(offset / 1024 / 1024).toFixed(1)} MB...`);
      }
    }

    updateProgress("backupProgressBar", 100);

    const fullBackup = new Uint8Array(flashSize);
    let position = 0;
    for (const chunk of chunks) {
      fullBackup.set(chunk, position);
      position += chunk.length;
    }

    const blob = new Blob([fullBackup], { type: "application/octet-stream" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `xteink-backup-${Date.now()}.bin`;
    a.click();
    URL.revokeObjectURL(url);

    log("Full backup complete!", "success");
    showStatus("backupStatus", "Backup saved successfully!", "success");
    hideProgress("backupProgressBar");
  } catch (error) {
    log(`Backup failed: ${error.message}`, "error");
    showStatus("backupStatus", `Backup failed: ${error.message}`, "error");
    hideProgress("backupProgressBar");
  }
}

// Restore full flash
export async function restoreFullFlash() {
  const fileInput = document.getElementById("restoreInput");
  const esploader = getEspLoader();

  if (!esploader) {
    showStatus("backupStatus", "Please connect to device first", "error");
    return;
  }

  if (!fileInput.files.length) {
    showStatus("backupStatus", "No backup file selected!", "error");
    return;
  }

  const file = fileInput.files[0];
  const sizeMB = file.size / (1024 * 1024);
  const EXPECTED_SIZE = 16 * 1024 * 1024; // 16 MB

  // Strict Size Check (Must be exactly 16MB)
  if (file.size !== EXPECTED_SIZE) {
    const errorMsg = `Error: Invalid Backup File Size!\n\nDetected: ${sizeMB.toFixed(2)} MB\nExpected: 16.00 MB (${EXPECTED_SIZE} bytes)\n\nFull System Restore requires an exact 16MB image matching the device flash size.`;
    log(errorMsg, "error");
    alert(errorMsg);
    return;
  }

  if (
    !confirm(
      `WARNING: You are about to RESTORE a 16MB Full System Backup.\nThis will completely overwrite ALL data on the chip (Firmware, NVS, Filesystem).\n\nAre you sure you want to proceed?`,
    )
  ) {
    return;
  }

  try {
    log(
      `Restoring Full Flash from ${file.name} (${sizeMB.toFixed(2)} MB)...`,
      "warning",
    );
    showStatus("backupStatus", "Restoring Flash... DO NOT UNPLUG.", "warning");

    const arrayBuffer = await file.arrayBuffer();
    const data = new Uint8Array(arrayBuffer);

    const binaryString = uint8ArrayToString(data);

    await esploader.writeFlash({
      fileArray: [{ data: binaryString, address: 0x0000 }],
      flashSize: "keep",
      eraseAll: false, // We overwrite, eraseAll usually safer but slower? writeFlash erases sector by sector usually.
      compress: true,
      reportProgress: (idx, written, total) => {
        updateProgress(
          "backupProgressBar",
          Math.round((written / total) * 100),
        );
      },
    });

    log("Full Restore complete!", "success");
    showStatus(
      "backupStatus",
      "Restore complete! Please press RESET then POWER button.",
      "success",
    );
    hideProgress("backupProgressBar");
  } catch (error) {
    log(`Restore failed: ${error.message}`, "error");
    showStatus("backupStatus", `Restore failed: ${error.message}`, "error");
    hideProgress("backupProgressBar");
  }
}

// Dump partition
export async function dumpPartition(name, offset, size) {
  const esploader = getEspLoader();
  if (!esploader) {
    log("Please connect to device first", "error");
    return;
  }

  try {
    log(
      `Dumping partition '${name}' (${(size / 1024 / 1024).toFixed(2)} MB)...`,
    );
    const data = await esploader.readFlash(offset, size);

    const blob = new Blob([data], { type: "application/octet-stream" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${name}-${Date.now()}.bin`;
    a.click();
    URL.revokeObjectURL(url);

    log(`Partition '${name}' dumped successfully`, "success");
  } catch (error) {
    log(`Failed to dump partition: ${error.message}`, "error");
  }
}
