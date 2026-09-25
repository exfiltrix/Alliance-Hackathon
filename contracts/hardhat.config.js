// Secrets come from backend/.env (gitignored) — the same file the backend reads.
require("dotenv").config({ path: require("path").join(__dirname, "..", "backend", ".env") });
require("@nomicfoundation/hardhat-toolbox");

const key = process.env.ANCHOR_PRIVATE_KEY;

module.exports = {
  solidity: "0.8.24",
  networks: {
    // `npx hardhat node` — offline demo chain on http://127.0.0.1:8545 (chain id 31337)
    localhost: { url: "http://127.0.0.1:8545" },
    sepolia: {
      url: process.env.SEPOLIA_RPC_URL || process.env.RPC_URL || "",
      accounts: key ? [key] : [],
      chainId: 11155111,
    },
  },
  etherscan: { apiKey: process.env.ETHERSCAN_API_KEY || "" },
};
