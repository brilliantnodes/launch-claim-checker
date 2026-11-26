// Two networks. Studio: free test accounts, try it yourself. Bradbury: GenLayer's
// public testnet (validators with real models and web access). The first contracts
// are on Phase 2; version 2 (checkerV2) is on Phase 3, live since 24 Nov 2026.
export const NETWORKS = {
  studio: {
    key: "studio",
    label: "Studio",
    name: "GenLayer Studio (studionet)",
    contract: "0x81351f3e6e7c9CFC41573Ca9962b17f70C9AFFB8",
    bounties: "0x583995CE8814C987e888070352A3F1d3AF9BBDca", // LaunchClaimBounties; set after each deployment
    checkerV2: "0x6eE60b9229490725d7C1E1Bc2DD80fabA5873878", // LaunchClaimCheckerV2 for the page (600-second windows), the build after review 5
    explorer: "https://explorer-studio.genlayer.com",
  },
  bradbury: {
    key: "bradbury",
    label: "Bradbury testnet",
    name: "GenLayer Testnet Bradbury Phase 2",
    contract: "0x963920f38a46c0Dc9592889a4B783FFAaEc6dA9C",
    bounties: "0xc437e39BA9e51282a259c814e2d4d9CcEF6c257b",
    checkerV2: "0x3DfF2C72398F1494a4f3962f1F1297f73649857b", // version 2 on Bradbury Phase 3 (live since 24 Nov 2026), 20-minute re-check window, the build after review 5
    checkerV2Rpc: "https://rpc.bradbury.genlayer.com", // the Phase 3 public node; the other contracts here are on Phase 2 (rpc below)
    explorer: "https://scan.bradbury.genlayer.com",
    rpc: "https://rpc-bradbury.genlayer.com",
    chainId: 4221,
    faucet: "https://testnet-faucet.genlayer.foundation",
  },
};
export const NET = NETWORKS[new URLSearchParams(location.search).get("net")] || NETWORKS.studio;
export const CONTRACT_ADDRESS = NET.contract;
export const NETWORK_NAME = NET.name;
export const EXPLORER_BASE = NET.explorer;
export const REPO_URL = "https://github.com/brilliantnodes/launch-claim-checker";
