import { createClient, createAccount, generatePrivateKey } from "genlayer-js";
import { studionet } from "genlayer-js/chains";
import { CONTRACT_ADDRESS, NETWORK_NAME, EXPLORER_BASE, REPO_URL } from "./config.js";

const $ = (id) => document.getElementById(id);
const el = (tag, cls, text) => {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text !== undefined) n.textContent = String(text); // always plain text
  return n;
};

// ---------------------------------------------------------------- clients

const reader = createClient({ chain: studionet });
let writer = null; // { client, address, kind }

// GenLayer returns maps and big integers. Turn them into plain values.
function plain(v) {
  if (v instanceof Map) return Object.fromEntries([...v.entries()].map(([k, x]) => [k, plain(x)]));
  if (Array.isArray(v)) return v.map(plain);
  if (typeof v === "bigint") return Number(v);
  if (v && typeof v === "object") return Object.fromEntries(Object.entries(v).map(([k, x]) => [k, plain(x)]));
  return v;
}

const read = async (functionName, args = []) =>
  plain(await reader.readContract({ address: CONTRACT_ADDRESS, functionName, args }));

// ----------------------------------------------------------------- wallet

function setWallet(next) {
  writer = next;
  $("wallet-state").textContent = next
    ? `${next.kind}: ${next.address.slice(0, 6)}…${next.address.slice(-4)}`
    : "No account connected.";
}

$("btn-temp").addEventListener("click", () => {
  const account = createAccount(generatePrivateKey());
  setWallet({
    client: createClient({ chain: studionet, account }),
    address: account.address,
    kind: "Temporary account",
  });
  showFormError("");
});

$("btn-mm").addEventListener("click", async () => {
  showFormError("");
  if (!window.ethereum) {
    showFormError("No browser wallet was found. Use a temporary Studio account instead, or install MetaMask.");
    return;
  }
  try {
    // Order matters. MetaMask only lets an account send on a network it was
    // approved for, so the Studio network is added first and the account is
    // approved after that.
    await useStudioNetwork();
    const accounts = await requestAccounts();
    if (!accounts || !accounts.length) throw new Error("The wallet returned no account.");
    const client = createClient({ chain: studionet, account: accounts[0] });
    setWallet({ client, address: accounts[0], kind: "MetaMask" });
  } catch (e) {
    showFormError(`The wallet did not connect: ${short(e)}`);
  }
});

// Ask for a fresh account approval, so it covers the Studio network even if
// this site was approved earlier on other networks only.
async function requestAccounts() {
  try {
    await window.ethereum.request({ method: "wallet_requestPermissions", params: [{ eth_accounts: {} }] });
    return await window.ethereum.request({ method: "eth_accounts" });
  } catch (e) {
    if (e && e.code === 4001) throw e; // the user said no
    return await window.ethereum.request({ method: "eth_requestAccounts" });
  }
}

// Ask the wallet to add the Studio network and switch to it. Nothing else
// is requested from the wallet: no extra permissions and no add-ons.
async function useStudioNetwork() {
  const chainId = `0x${studionet.id.toString(16)}`;
  const current = await window.ethereum.request({ method: "eth_chainId" });
  if (String(current).toLowerCase() === chainId) return;
  try {
    await window.ethereum.request({ method: "wallet_switchEthereumChain", params: [{ chainId }] });
  } catch {
    await window.ethereum.request({
      method: "wallet_addEthereumChain",
      params: [
        {
          chainId,
          chainName: studionet.name,
          rpcUrls: studionet.rpcUrls.default.http,
          nativeCurrency: studionet.nativeCurrency,
        },
      ],
    });
    await window.ethereum.request({ method: "wallet_switchEthereumChain", params: [{ chainId }] });
  }
}

// ------------------------------------------------------------------- form

const SITE = "https://checker.brilliantnodes.com";
// Examplecoin and Controlcoin are fictional. Their pages are test pages
// hosted with this site: Examplecoin's claims fail, Controlcoin's hold.
const ex = (coin, page, ctype, ctext) => ({
  ann: `${SITE}/examples/${coin}-announcement.html`,
  exp: `${SITE}/examples/${coin}-explorer-${page}.html`,
  ctype,
  ctext,
});
const EXAMPLES = {
  exmMining: ex("examplecoin", "mining", "DECENTRALIZED_MINING", "Mining is decentralized: hundreds of independent miners secure the network."),
  exmFounder: ex("examplecoin", "block1", "NO_FOUNDER_REWARD", "No founder reward and no developer tax."),
  ctlFounder: ex("controlcoin", "block1", "NO_FOUNDER_REWARD", "No founder reward and no developer tax."),
  ctlMining: ex("controlcoin", "mining", "DECENTRALIZED_MINING", "Mining is decentralized: no single miner produces most of the blocks."),
};

document.querySelectorAll("[data-example]").forEach((b) =>
  b.addEventListener("click", () => {
    const ex = EXAMPLES[b.dataset.example];
    $("ann").value = ex.ann;
    $("exp").value = ex.exp;
    $("ctype").value = ex.ctype;
    $("ctext").value = ex.ctext;
    syncClaimText();
  })
);

function syncClaimText() {
  const custom = $("ctype").value === "CUSTOM";
  $("ctext-opt").textContent = custom ? "(required)" : "(optional)";
}
$("ctype").addEventListener("change", syncClaimText);

function showFormError(msg) {
  $("form-error").textContent = msg;
  $("form-error").hidden = !msg;
}

const short = (e) => String((e && (e.shortMessage || e.message)) || e).slice(0, 300);

function validUrl(v) {
  try {
    const u = new URL(v);
    return (u.protocol === "http:" || u.protocol === "https:") && v.length <= 300;
  } catch {
    return false;
  }
}

$("form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  showFormError("");
  const ann = $("ann").value.trim();
  const exp = $("exp").value.trim();
  const ctype = $("ctype").value;
  const ctext = $("ctext").value.trim();
  if (!validUrl(ann)) return showFormError("Enter the announcement page as a full http or https address.");
  if (!validUrl(exp)) return showFormError("Enter the explorer page as a full http or https address.");
  if (ctype === "CUSTOM" && !ctext) return showFormError("Write the claim for an 'Other claim' check.");
  if (!writer) return showFormError("Connect an account first: a temporary Studio account is enough.");
  await runCheck([ann, exp, ctype, ctext]);
});

// -------------------------------------------------- transaction lifecycle

const STEPS = [
  ["SENT", "Sent", "The transaction was signed and sent."],
  ["PENDING", "Queued", "Waiting for a leader to be chosen."],
  ["PROPOSING", "Leader reads the pages", "One validator fetches both pages and proposes the facts and the verdict."],
  ["COMMITTING", "Validators check", "The other validators read the pages themselves and vote."],
  ["REVEALING", "Votes revealed", "Votes are opened and counted."],
  ["ACCEPTED", "Accepted", "A majority agreed. The check is recorded."],
];
const ORDER = STEPS.map((s) => s[0]);
const FINAL_BAD = {
  UNDETERMINED: "The validators did not agree, so nothing was recorded. This is the safe outcome when pages are unclear or changing. You can run the check again.",
  CANCELED: "The transaction was cancelled. Nothing was recorded.",
  LEADER_TIMEOUT: "The leader did not answer in time. Nothing was recorded. You can run the check again.",
  VALIDATORS_TIMEOUT: "The validators did not answer in time. Nothing was recorded. You can run the check again.",
};

function drawSteps(current, failed) {
  const ol = $("steps");
  ol.replaceChildren();
  const at = current === "FINALIZED" ? ORDER.length - 1 : ORDER.indexOf(current);
  STEPS.forEach(([key, title, help], i) => {
    const li = el("li");
    const state = failed && i >= Math.max(at, 0) ? (i === Math.max(at, 0) ? "failed" : "todo") : i < at ? "done" : i === at ? (key === "ACCEPTED" ? "done" : "now") : "todo";
    li.className = state;
    li.append(el("strong", null, title), el("span", null, help));
    ol.append(li);
  });
}

function statusOf(tx) {
  return String(tx?.statusName ?? tx?.status_name ?? tx?.status ?? "").toUpperCase();
}

async function runCheck(args) {
  const btn = $("submit");
  btn.disabled = true;
  $("life").hidden = false;
  $("life-result").replaceChildren();
  $("life-hash").textContent = "";
  $("life-note").textContent = "Waiting for the account to sign…";
  drawSteps("", false);
  $("life").scrollIntoView({ behavior: "smooth", block: "start" });

  let before = 0;
  try {
    before = await read("get_count");
  } catch {}

  let hash;
  try {
    hash = await writer.client.writeContract({
      address: CONTRACT_ADDRESS,
      functionName: "check_claim",
      args,
      value: 0n,
    });
  } catch (e) {
    $("life-note").textContent =
      e && e.code === 4100
        ? "Your wallet has not approved this account for the Studio network. Click Connect MetaMask again, approve the account, and run the check again."
        : `The transaction was not sent: ${short(e)}`;
    drawSteps("SENT", true);
    btn.disabled = false;
    return;
  }

  $("life-hash").replaceChildren(el("span", null, "Transaction: "), el("code", null, hash));
  drawSteps("SENT", false);
  $("life-note").textContent = "Sent. A check usually takes one to three minutes, longer when the network is busy.";

  let last = "SENT";
  let final = null;
  const started = Date.now();
  while (Date.now() - started < 6 * 60 * 1000) {
    await new Promise((r) => setTimeout(r, 3000));
    let tx;
    try {
      tx = await reader.getTransaction({ hash });
    } catch {
      continue; // the node may not know the transaction yet
    }
    const st = statusOf(tx);
    if (!st) continue;
    if (st !== last && (ORDER.includes(st) || st === "FINALIZED")) {
      last = st;
      drawSteps(st, false);
    }
    if (st === "ACCEPTED" || st === "FINALIZED") {
      final = { ok: true, tx };
      break;
    }
    if (FINAL_BAD[st]) {
      final = { ok: false, st, tx };
      break;
    }
  }

  if (!final) {
    $("life-note").textContent = "Still not settled after six minutes. The transaction may yet complete. Use Refresh below to look for it later.";
    btn.disabled = false;
    return;
  }
  if (!final.ok) {
    drawSteps(last, true);
    $("life-note").textContent = FINAL_BAD[final.st];
    btn.disabled = false;
    return;
  }
  $("life-note").textContent = "Accepted. Reading the recorded result…";

  // Accepted does not always mean recorded: the contract refuses bad input
  // or an unreadable explorer page, and that refusal is itself agreed on.
  let after = before;
  try {
    after = await read("get_count");
  } catch {}
  if (after > before) {
    const mine = (await read("get_latest", [5])).find((c) => c.submitter.toLowerCase() === writer.address.toLowerCase());
    $("life-note").textContent = "Accepted by a majority of validators and recorded.";
    if (mine) $("life-result").append(checkCard(mine));
  } else {
    drawSteps("REVEALING", true);
    $("life-note").textContent =
      "The validators agreed that the check could not be carried out, most often because the explorer page could not be read. Nothing was recorded. Try a page that shows its data without scripts.";
  }
  btn.disabled = false;
  loadRecent();
}

// ----------------------------------------------------------------- render

const VERDICT_LABEL = { supported: "Supported", contradicted: "Contradicted", undetermined: "Undetermined" };
const CLAIM_LABEL = {
  NO_PREMINE: "No premine",
  NO_FOUNDER_REWARD: "No founder reward",
  FAIR_LAUNCH: "Fair launch",
  DECENTRALIZED_MINING: "Decentralized mining",
  CUSTOM: "Other claim",
};
const RULE_TEXT = {
  M1_TOP_MINER_ABOVE_HALF: "One miner produced more than half of the inspected blocks.",
  M2_TOP_MINER_AT_OR_BELOW_THIRD: "The largest miner produced a third or less of the inspected blocks.",
  P1_EARLY_ALLOCATION_FOUND: "The explorer shows an extra allocation in the earliest blocks.",
  P2_EARLY_BLOCKS_SHOWN_CLEAN: "The explorer shows the earliest blocks with only the ordinary mining reward.",
  E1_EXPLORER_CONTRADICTS: "The explorer data goes against the claim.",
  A1_ANNOUNCEMENT_CONTRADICTS: "The announcement itself goes against the claim.",
  C1_EXPLORER_SUPPORTS: "The explorer data agrees with the claim.",
  U1_NOT_ENOUGH_EVIDENCE: "The pages did not show enough evidence either way.",
};

function linkTo(url) {
  const a = el("a", null, url);
  // Only http(s) links are ever made clickable.
  if (/^https?:\/\//i.test(url)) {
    a.href = url;
    a.target = "_blank";
    a.rel = "noopener noreferrer nofollow";
  }
  return a;
}

function checkCard(c) {
  const card = el("article", `check ${c.verdict}`);
  const head = el("div", "check-head");
  head.append(el("span", `badge ${c.verdict}`, VERDICT_LABEL[c.verdict] || c.verdict));
  head.append(el("span", "claim", CLAIM_LABEL[c.claim_type] || c.claim_type));
  head.append(el("span", "small", `#${c.id} · ${fmtTime(c.checked_at)}`));
  card.append(head);

  if (c.claim_text) card.append(el("p", "quote", `“${c.claim_text}”`));
  card.append(el("p", "why", RULE_TEXT[c.rule] || c.rule));

  const facts = el("dl", "facts");
  const f = c.facts || {};
  const add = (k, v) => {
    facts.append(el("dt", null, k), el("dd", null, v));
  };
  if (f.top_miner_share_bp !== null && f.top_miner_share_bp !== undefined)
    add("Top miner's share", `${(f.top_miner_share_bp / 100).toFixed(2)}%`);
  if (f.blocks_inspected !== null && f.blocks_inspected !== undefined) add("Blocks inspected", f.blocks_inspected);
  add("Early extra allocation", { yes: "Found", no: "None in the blocks shown", not_shown: "Earliest blocks not shown" }[f.early_allocation_found] || "Unknown");
  add("Explorer page", { supports: "Agrees with the claim", contradicts: "Goes against the claim", silent: "Shows nothing usable" }[f.ev_direction] || "Unknown");
  add("Announcement page", f.announcement_read === false ? "Could not be read" : { supports: "Agrees with the claim", contradicts: "Goes against the claim", silent: "Says nothing usable" }[f.ann_direction] || "Unknown");
  card.append(facts);

  const src = el("p", "small src");
  src.append(el("span", null, "Announcement: "), linkTo(c.announcement_url), el("br"), el("span", null, "Explorer: "), linkTo(c.explorer_url));
  card.append(src);

  if (Array.isArray(c.reasons) && c.reasons.length) {
    const d = el("details");
    d.append(el("summary", null, "Notes from one validator (not verified by the others)"));
    const ul = el("ul");
    c.reasons.forEach((r) => ul.append(el("li", null, r)));
    d.append(ul);
    card.append(d);
  }
  card.append(el("p", "small", `Requested by ${c.submitter}`));
  return card;
}

function fmtTime(s) {
  const d = new Date(s);
  return isNaN(d) ? String(s) : d.toISOString().replace("T", " ").slice(0, 16) + " UTC";
}

async function loadRecent() {
  $("recent-state").textContent = "Loading…";
  try {
    const list = await read("get_latest", [20]);
    const box = $("recent");
    box.replaceChildren();
    if (!list.length) {
      $("recent-state").textContent = "No checks recorded yet. Run the first one above.";
      return;
    }
    $("recent-state").textContent = `${list.length} most recent, newest first.`;
    list.forEach((c) => box.append(checkCard(c)));
  } catch (e) {
    $("recent-state").textContent = `The contract could not be read: ${short(e)}`;
  }
}
$("refresh").addEventListener("click", loadRecent);

async function loadRules() {
  try {
    const r = await read("get_rules");
    const pct = (bp) => `${bp / 100}%`;
    const rows = [
      ["Decentralized mining: contradicted", `Top miner above ${pct(r.contradict_share_bp)} of at least ${r.min_blocks} blocks`],
      ["Decentralized mining: supported", `Top miner at or below ${pct(r.support_share_bp)} of at least ${r.min_blocks} blocks`],
      ["No premine / no founder reward: contradicted", "An extra allocation in the earliest blocks, or a page that goes against the claim"],
      ["No premine / no founder reward: supported", "Earliest blocks shown with only the ordinary reward, and the explorer agrees"],
      ["Anything else", "Undetermined"],
      ["Validators' tolerance on the top miner's share", `${r.share_tolerance_bp / 100} percentage points`],
      ["Text read from each page", `First ${r.page_chars.toLocaleString("en")} characters`],
    ];
    const t = $("rules");
    t.replaceChildren();
    rows.forEach(([a, b]) => {
      const tr = el("tr");
      tr.append(el("th", null, a), el("td", null, b));
      t.append(tr);
    });
  } catch {}
}

// ------------------------------------------------------------------- boot

$("net").append(el("span", "dot"), el("span", null, NETWORK_NAME));
const fc = $("foot-contract");
fc.append(el("span", null, "Contract: "));
const ca = el("a", null, CONTRACT_ADDRESS);
ca.href = `${EXPLORER_BASE}/address/${CONTRACT_ADDRESS}`;
ca.target = "_blank";
ca.rel = "noopener noreferrer";
fc.append(ca);
$("foot-repo").href = REPO_URL;
syncClaimText();
loadRecent();
loadRules();
