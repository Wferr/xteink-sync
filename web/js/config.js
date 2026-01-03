// FIRMWARE CONFIGURATION - Loads from separate patch files
// ========================================================================

import { log } from "./utils.js";

// Firmware configuration - will be loaded on init
export let FIRMWARE_CONFIG = null;

// Available firmware versions
export let FIRMWARE_VERSIONS = null;

// Load available firmware versions
export async function loadFirmwareVersions() {
  try {
    const response = await fetch("patches/versions.json");
    if (!response.ok) {
      throw new Error(`Failed to load versions: ${response.status}`);
    }
    FIRMWARE_VERSIONS = await response.json();
    return FIRMWARE_VERSIONS;
  } catch (error) {
    log("Error loading firmware versions: " + error.message, "error");
    throw error;
  }
}

// Load firmware configuration from JSON file
export async function loadFirmwareConfig(version) {
  try {
    const response = await fetch(`patches/${version}.json`);
    if (!response.ok) {
      throw new Error(`Failed to load patch config: ${response.status}`);
    }
    FIRMWARE_CONFIG = await response.json();
    return FIRMWARE_CONFIG;
  } catch (error) {
    log("Error loading firmware config: " + error.message, "error");
    throw error;
  }
}
