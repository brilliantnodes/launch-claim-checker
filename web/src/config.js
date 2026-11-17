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
    explorer: "https://explorer-studio.genlayer.com",
  },
  bradbury: {
    key: "bradbury",
    label: "Bradbury testnet",
    name: "GenLayer Testnet Bradbury Phase 2",
    contract: "0x963920f38a46c0Dc9592889a4B783FFAaEc6dA9C",
    bounties: "0xc437e39BA9e51282a259c814e2d4d9CcEF6c257b",
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
