import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Allows accessing the dev server (and its HMR websocket) from other devices on the LAN.
  allowedDevOrigins: ["192.168.68.86"],
};

export default nextConfig;
