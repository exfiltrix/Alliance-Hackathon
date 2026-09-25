import os from "node:os";
import type { NextConfig } from "next";

// Opening the dev server from another device (http://<LAN IP>:3000) needs that host allowed.
// Every IPv4 address of this machine at startup is allowed; restart `npm run dev` after changing Wi-Fi.
const lanHosts = Object.values(os.networkInterfaces())
  .flat()
  .filter((a) => a && a.family === "IPv4" && !a.internal)
  .map((a) => a!.address);

const nextConfig: NextConfig = {
  agentRules: false,
  allowedDevOrigins: lanHosts,
};

export default nextConfig;
