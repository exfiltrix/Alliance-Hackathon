// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @title MedSeal ledger anchor
/// @notice Stores Merkle roots of batches of MedSeal ledger entries. Only hashes: never images,
///         never patient data. There is no update or delete: history is append-only by construction.
contract MedSealAnchor {
    address public immutable owner;
    struct Anchor { bytes32 root; uint64 time; uint32 count; }
    Anchor[] public anchors;
    mapping(bytes32 => bool) public anchored;
    event Anchored(uint256 indexed id, bytes32 root, uint32 count);

    constructor() { owner = msg.sender; }

    function anchor(bytes32 root, uint32 count) external returns (uint256 id) {
        require(msg.sender == owner, "only MedSeal");
        require(!anchored[root], "already anchored");
        anchors.push(Anchor(root, uint64(block.timestamp), count));
        anchored[root] = true;
        id = anchors.length - 1;
        emit Anchored(id, root, count);
    }

    function total() external view returns (uint256) { return anchors.length; }
}
