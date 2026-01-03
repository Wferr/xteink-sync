// ========================================================================
// ESP32 CONNECTION MANAGEMENT
// ========================================================================

import { log } from "./utils.js";
import { readPartitionTable, readOtaData } from "./ota.js";

let device, transport, chip, esploader;

export function getEspLoader() {
  return esploader;
}

export async function connect(ESPLoader, Transport) {
  try {
    const baudrate = parseInt(document.getElementById("baudrateSelect").value);
    log(`Requesting serial port at ${baudrate} baud...`);

    device = await navigator.serial.requestPort({});
    transport = new Transport(device, true);

    log("Connecting to ESP32...");

    // Capture MAC address from terminal output
    let macAddress = null;

    esploader = new ESPLoader({
      transport: transport,
      baudrate: baudrate,
      terminal: {
        clean() {},
        writeLine(data) {
          log(data);
          // Extract MAC address from log
          const macMatch = data.match(/MAC:\s+([0-9a-f:]+)/i);
          if (macMatch) {
            macAddress = macMatch[1];
          }
        },
        write(data) {
          log(data);
        },
      },
    });

    chip = await esploader.main();
    log(`Connected! Chip: ${chip}`, "success");

    // Display chip info with MAC if available
    const chipInfoText = macAddress
      ? `${chip} | MAC: ${macAddress} | Baud: ${baudrate}`
      : `${chip} | Baud: ${baudrate}`;
    document.getElementById("chipInfo").textContent = chipInfoText;

    // Update toggle button
    const connectBtn = document.getElementById("connectBtn");
    connectBtn.setAttribute("data-connected", "true");
    connectBtn.classList.remove("primary");
    connectBtn.classList.add("error");
    connectBtn.textContent = "Disconnect"; // Text content update (was span id)

    window.esploader = esploader;

    // Auto-read partition table and OTA data
    log("Reading partition table...", "info");
    await readPartitionTable(esploader);

    log("Reading OTA partition status...", "info");
    await readOtaData(esploader);

    return esploader;
  } catch (error) {
    log(`Connection failed: ${error.message}`, "error");
    alert(`Connection failed: ${error.message}`);
    return null;
  }
}

export async function disconnect() {
  if (transport) {
    await transport.disconnect();
    await transport.waitForUnlock(1500);
  }

  // Update toggle button
  const connectBtn = document.getElementById("connectBtn");
  connectBtn.setAttribute("data-connected", "false");
  connectBtn.classList.remove("error");
  connectBtn.classList.add("primary");
  connectBtn.textContent = "Connect"; // Text content update

  document.getElementById("chipInfo").textContent = "Not connected";

  log("Disconnected");
}
