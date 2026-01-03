/**
 * Xteink QR Code Parser
 * Ports the logic from xteink-sync Python CLI (src/xteink/client.py)
 */

export function parseQrCode(qrHex) {
  if (!qrHex) throw new Error("Empty QR code hex string");

  // Clean input
  qrHex = qrHex.trim();

  // Known XOR Key
  const KEY_HEX =
    "600a7a210b7729504c6e3b4276afe52068db6a162a2f270f057217685d01";

  // Helper: Hex String to Uint8Array
  const hexToBytes = (hex) => {
    if (hex.length % 2 !== 0) {
      throw new Error("Invalid hex string length");
    }
    const bytes = new Uint8Array(hex.length / 2);
    for (let c = 0; c < hex.length; c += 2) {
      bytes[c / 2] = parseInt(hex.substr(c, 2), 16);
    }
    return bytes;
  };

  try {
    const key = hexToBytes(KEY_HEX);
    const data = hexToBytes(qrHex);
    const decrypted = new Uint8Array(data.length);

    // XOR Decrypt
    for (let i = 0; i < data.length; i++) {
      decrypted[i] = data[i] ^ key[i % key.length];
    }

    // Helper: Decode text slice (utf-8) and strip nulls
    const decodeSlice = (start, end) => {
      if (start >= decrypted.length) return "";
      const slice = decrypted.subarray(start, Math.min(end, decrypted.length));
      const decoder = new TextDecoder("utf-8");
      let text = decoder.decode(slice);
      // Emulate Python's errors="ignore": remove replacement characters
      text = text.replace(/\uFFFD/g, "");
      // Remove null characters and whitespace
      return text.replace(/\0/g, "").trim();
    };

    // Extract Fields
    // 0:6   : Brand
    // 6:13  : Device Type
    // 13:19 : MAC Bytes (6 bytes)
    // 19:30 : Version

    const brand = decodeSlice(0, 6);
    const deviceType = decodeSlice(6, 13);

    const macBytes = decrypted.subarray(13, 19);
    const macAddress = Array.from(macBytes)
      .map((b) => b.toString(16).toUpperCase().padStart(2, "0"))
      .join(":");

    // Device ID Int: bytes 3,4,5 of mac (Big Endian)
    // Indices 16, 17, 18 in the decrypted array
    let devIdInt = 0;
    if (macBytes.length >= 6) {
      devIdInt = (macBytes[3] << 16) | (macBytes[4] << 8) | macBytes[5];
    }

    const version = decodeSlice(19, 30);

    const macUnderscore = Array.from(macBytes)
      .map((b) => b.toString(16).toUpperCase().padStart(2, "0"))
      .join("_");

    const fullDeviceId = `${devIdInt}_${macUnderscore}`;

    return {
      success: true,
      brand,
      deviceType,
      macAddress,
      version,
      deviceId: fullDeviceId,
      decryptedHex: Array.from(decrypted)
        .map((b) => b.toString(16).padStart(2, "0"))
        .join(""),
    };
  } catch (error) {
    console.error("QR Parse Error:", error);
    return {
      success: false,
      error: error.message,
    };
  }
}
