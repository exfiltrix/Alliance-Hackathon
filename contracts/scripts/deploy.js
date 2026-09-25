// npx hardhat run scripts/deploy.js --network localhost | sepolia
// Prints the lines to put into backend/.env.
const hre = require("hardhat");

async function main() {
  const [deployer] = await hre.ethers.getSigners();
  const Anchor = await hre.ethers.getContractFactory("MedSealAnchor");
  const contract = await Anchor.deploy();
  await contract.waitForDeployment();
  const address = await contract.getAddress();
  const { chainId } = await hre.ethers.provider.getNetwork();
  console.log(`MedSealAnchor deployed by ${deployer.address}`);
  console.log(`CONTRACT_ADDRESS=${address}`);
  console.log(`CHAIN_ID=${chainId}`);
  if (hre.network.name === "sepolia") {
    console.log("EXPLORER_URL=https://sepolia.etherscan.io");
    console.log(`verify source: npx hardhat verify --network sepolia ${address}`);
  }
}

main().catch((e) => { console.error(e); process.exitCode = 1; });
