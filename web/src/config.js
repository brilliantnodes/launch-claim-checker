// Two networks. Studio: free test accounts, try it yourself. Bradbury Phase 2:
// GenLayer's public testnet (validators with real models and web access); the
// live record, and checks from a wallet holding Bradbury test GEN.
export const NETWORKS = {
  studio: {
    key: "studio",
    label: "Studio",
    name: "GenLayer Studio (studionet)",
    contract: "0x81351f3e6e7c9CFC41573Ca9962b17f70C9AFFB8",
    bounties: "0x583995CE8814C987e888070352A3F1d3AF9BBDca", // LaunchClaimBounties; set after each deployment
    checkerV2: "0x624c4Af62668A6ac6C82040F61d9d0dDaCEa49F9", // LaunchClaimCheckerV2 for the page (600-second windows), the build after review 3
    explorer: "https://explorer-studio.genlayer.com",
  },
  bradbury: {
    key: "bradbury",
    label: "Bradbury testnet",
    name: "GenLayer Testnet Bradbury Phase 2",
    contract: "0x963920f38a46c0Dc9592889a4B783FFAaEc6dA9C",
    bounties: "0xc437e39BA9e51282a259c814e2d4d9CcEF6c257b",
    checkerV2: "0xBa377D0FED0E0A40eA3978716F4495D234DF6e46", // version 2 on Bradbury Phase 3 (live since 24 Nov 2026), 20-minute re-check window
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
