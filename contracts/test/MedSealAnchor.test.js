const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("MedSealAnchor", function () {
  const root = ethers.keccak256(ethers.toUtf8Bytes("batch-1"));

  async function deploy() {
    const [owner, other] = await ethers.getSigners();
    const contract = await (await ethers.getContractFactory("MedSealAnchor")).deploy();
    return { contract, owner, other };
  }

  it("owner anchors a root: stored, flagged, event emitted", async function () {
    const { contract } = await deploy();
    await expect(contract.anchor(root, 7)).to.emit(contract, "Anchored").withArgs(0, root, 7);
    const a = await contract.anchors(0);
    expect(a.root).to.equal(root);
    expect(a.count).to.equal(7);
    expect(await contract.anchored(root)).to.equal(true);
    expect(await contract.total()).to.equal(1);
  });

  it("non-owner anchor reverts", async function () {
    const { contract, other } = await deploy();
    await expect(contract.connect(other).anchor(root, 1)).to.be.revertedWith("only MedSeal");
  });

  it("duplicate root reverts", async function () {
    const { contract } = await deploy();
    await contract.anchor(root, 1);
    await expect(contract.anchor(root, 1)).to.be.revertedWith("already anchored");
  });

  it("has no way to change or delete an anchor", async function () {
    const { contract } = await deploy();
    const writers = contract.interface.fragments
      .filter((f) => f.type === "function" && !["view", "pure"].includes(f.stateMutability))
      .map((f) => f.name);
    expect(writers).to.deep.equal(["anchor"]);
  });
});
