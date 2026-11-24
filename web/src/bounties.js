import { createClient, createAccount, generatePrivateKey, abi } from "genlayer-js";
import { studionet } from "genlayer-js/chains";
// Since late November 2026 GenLayer Studio refuses a transaction without a fee distribution.
// Reads stay on genlayer-js 1; every write goes through genlayer-js 2 with a fee estimate
// (about 0.1 test GEN deposited, the unused part refunded).
import { createClient as createWriter, createAccount as createAccountW } from "genlayer-js-studio";
import { studionet as studionetW } from "genlayer-js-studio/chains";
const studioFees = async (w) => { const f = await w.estimateTransactionFees(); return { distribution: f.distribution, feeValue: f.feeValue }; };
import { NET, NETWORKS, EXPLORER_BASE, REPO_URL } from "./config.js";

// Claim bounties (contracts/launch_claim_bounties.py). On Studio the page
// posts, files, judges and withdraws with temporary accounts. The Bradbury
// view only reads the record there, so it needs no wallet.
const BRADBURY = NET.key === "bradbury";
const ADDRESS = NET.bounties || "";
const v2 = BRADBURY ? await import("genlayer-js-v2") : null;
const v2chains = BRADBURY ? await import("genlayer-js-v2/chains") : null;

const $ = (id) => document.getElementById(id);
const el = (tag, cls, text) => {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text !== undefined) n.textContent = String(text); // always plain text
  return n;
};
const link = (href, text) => {
  const a = el("a", null, text);
  // Only http(s) links are ever made clickable.
  if (/^https?:\/\//i.test(href)) {
    a.href = href;
    a.target = "_blank";
    a.rel = "noopener noreferrer nofollow";
  }
  return a;
};
const RPC = studionet.rpcUrls.default.http[0];
const reader = BRADBURY ? v2.createClient({ chain: v2chains.testnetBradbury, endpoint: NET.rpc }) : createClient({ chain: studionet });

function plain(v) {
  if (v instanceof Map) return Object.fromEntries([...v.entries()].map(([k, x]) => [k, plain(x)]));
  if (Array.isArray(v)) return v.map(plain);
  if (typeof v === "bigint") return Number(v);
  if (v && typeof v === "object") return Object.fromEntries(Object.entries(v).map(([k, x]) => [k, plain(x)]));
  return v;
}
const read = async (functionName, args = []) => plain(await reader.readContract({ address: ADDRESS, functionName, args }));
const short = (e) => String((e && (e.shortMessage || e.message)) || e).slice(0, 300);
const shortAddr = (a) => (a ? `${a.slice(0, 6)}…${a.slice(-4)}` : "");
const same = (a, b) => !!a && !!b && a.toLowerCase() === b.toLowerCase();
const nowS = () => Math.floor(Date.now() / 1000);
const when = (s) => (s ? new Date(s * 1000).toISOString().replace("T", " ").slice(0, 16) + " UTC" : "");

function toWei(text) {
  const s = String(text).trim();
  if (!/^\d+(\.\d{1,18})?$/.test(s)) return null;
  const [w, f = ""] = s.split(".");
  return BigInt(w) * 10n ** 18n + BigInt((f + "0".repeat(18)).slice(0, 18));
}
function gen(wei) {
  const n = BigInt(wei);
  const w = n / 10n ** 18n;
  const f = (n % 10n ** 18n).toString().padStart(18, "0").replace(/0+$/, "");
  return `${w}${f ? "." + f : ""} GEN`;
}

// ------------------------------------------------------------ sealed claims

// A filing carries only sha256("<bounty id>|<address, lower case>|<rule>|<block>|<salt>").
// The rule, block and salt stay in this browser until the filer has the filing judged.
const memory = new Map();
const sealedKey = (address, id) => `lcb.sealed.${ADDRESS.toLowerCase()}.${address.toLowerCase()}.${id}`;
function sealedList(address, id) {
  const k = sealedKey(address, id);
  try { return JSON.parse(localStorage.getItem(k) || "null") || memory.get(k) || []; } catch { return memory.get(k) || []; }
}
function keepSealed(address, id, claim) {
  const k = sealedKey(address, id);
  const list = [...sealedList(address, id), claim].slice(-20);
  memory.set(k, list);
  try { localStorage.setItem(k, JSON.stringify(list)); } catch {}
}
const hex = (bytes) => [...bytes].map((x) => x.toString(16).padStart(2, "0")).join("");
async function seal(id, address, rule, height) {
  const salt = hex(crypto.getRandomValues(new Uint8Array(16)));
  const text = `${id}|${address.toLowerCase()}|${rule}|${height}|${salt}`;
  const digest = hex(new Uint8Array(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text))));
  return { rule, height, salt, digest };
}

// ----------------------------------------------------------------- accounts

const ROLE_LABEL = { poster: "Poster", hunter: "Hunter", second: "Second hunter" };
const roles = { poster: null, hunter: null, second: null };
const store = {
  get: (k) => { try { return localStorage.getItem(k); } catch { return null; } },
  set: (k, v) => { try { localStorage.setItem(k, v); } catch {} },
};
function tempAccount(role) {
  let key = store.get(`lcb.temp.${role}`);
  if (!key) {
    key = generatePrivateKey();
    store.set(`lcb.temp.${role}`, key);
  }
  const account = createAccount(key);
  roles[role] = { client: createWriter({ chain: studionetW, account: createAccountW(key) }), address: account.address, role };
  $(`${role}-addr`).textContent = `Temporary: ${account.address}`;
  refreshBalances();
  loadList();
}
async function faucet(address) {
  const body = `{"jsonrpc":"2.0","id":1,"method":"sim_fundAccount","params":["${address}",20000000000000000000]}`;
  const r = await fetch(RPC, { method: "POST", headers: { "content-type": "application/json" }, body });
  const j = await r.json();
  if (j.error) throw new Error(j.error.message || "faucet error");
}
async function refreshBalances() {
  for (const role of Object.keys(roles)) {
    const r = roles[role];
    const box = $(`${role}-bal`);
    box.textContent = "";
    if (!r || !ADDRESS) continue;
    try {
      const [bal, claim] = await Promise.all([reader.getBalance({ address: r.address }), read("get_claimable", [r.address])]);
      box.textContent = `Wallet: ${gen(bal)}. Credited by the contract: ${gen(claim)}.`;
      if (BigInt(claim) > 0n) {
        const b = el("button", "secondary", "Withdraw");
        b.type = "button";
        b.addEventListener("click", () => send(r, "withdraw", [0], 0n, `${ROLE_LABEL[role]} withdraws ${gen(claim)}`));
        box.append(" ", b);
      }
    } catch {}
  }
}
const acctError = (m) => { $("acct-error").textContent = m; $("acct-error").hidden = !m; };
document.querySelectorAll("[data-temp]").forEach((b) => b.addEventListener("click", () => { acctError(""); tempAccount(b.dataset.temp); }));
document.querySelectorAll("[data-fund]").forEach((b) => b.addEventListener("click", async () => {
  const r = roles[b.dataset.fund];
  acctError("");
  if (!r) return acctError(`Choose a ${ROLE_LABEL[b.dataset.fund].toLowerCase()} account first.`);
  b.disabled = true;
  try { await faucet(r.address); await new Promise((x) => setTimeout(x, 1500)); await refreshBalances(); } catch (e) { acctError(`Faucet: ${short(e)}`); }
  b.disabled = false;
}));

// -------------------------------------------------- transaction lifecycle

const STEPS = [
  ["SENT", "Sent", "Signed in this browser and sent."],
  ["PENDING", "Queued", "Waiting for a leader."],
  ["PROPOSING", "Leader works", "One validator runs the step; for a judgement it reads the pinned page now."],
  ["COMMITTING", "Validators check", "The others run it on their own and vote."],
  ["REVEALING", "Votes revealed", "Votes are opened and counted."],
  ["ACCEPTED", "Accepted", "A majority agreed; the new state is recorded and any payout is credited."],
  ["FINALIZED", "Finalized", "The appeal window has passed. A withdrawal's GEN reaches the wallet now."],
];
const ORDER = STEPS.map((s) => s[0]);
const FINAL_BAD = {
  UNDETERMINED: "The validators did not agree, so nothing changed. A filing stays live: it can be judged again inside its 30 minutes.",
  CANCELED: "The transaction was cancelled. Nothing changed.",
  LEADER_TIMEOUT: "The leader did not answer in time. The network may still run this transaction after rotating the leader: check it on the explorer before trying again.",
  VALIDATORS_TIMEOUT: "The validators did not answer in time. The network may still run this transaction: check it on the explorer before trying again.",
};
const statusOf = (tx) => String(tx?.statusName ?? tx?.status_name ?? "").toUpperCase();
function drawSteps(cur, failed) {
  const ol = $("steps");
  ol.replaceChildren();
  const at = ORDER.indexOf(cur);
  STEPS.forEach(([key, title, help], i) => {
    const li = el("li");
    li.className = failed && i >= Math.max(at, 0) ? (i === Math.max(at, 0) ? "failed" : "todo") : i < at ? "done" : i === at ? (key === "FINALIZED" ? "done" : "now") : "todo";
    li.append(el("strong", null, title), el("span", null, help));
    ol.append(li);
  });
}
function leaderAnswer(tx) {
  try {
    const lr = tx?.consensus_data?.leader_receipt;
    const r = (Array.isArray(lr) ? lr[0] : lr)?.result;
    if (!r) return null;
    const p = r.payload;
    if (r.status === "rollback") return { reverted: String(typeof p === "string" ? p : (p && p.readable) || "the call was refused") };
    // The call's return value, decoded from GenLayer calldata bytes.
    if (p && Array.isArray(p.raw)) { const v = plain(abi.calldata.decode(new Uint8Array(p.raw))); return v && typeof v === "object" ? v : null; }
    return null;
  } catch { return null; }
}
const OUTCOME_TEXT = {
  PAYS_P1: "the block creates coins beyond the ordinary block reward",
  PAYS_M1: "one named miner has more than half of the blocks",
  NO_PAY: "the page does not show what the rule needs; the filing is used up",
  WRONG_PAGE: "the page shows another block number or does not name the coin; the filing stays live",
  UNREADABLE: "the page could not be read; the filing stays live",
};

let busy = false;
function setButtons(on) {
  document.querySelectorAll("#list button, #btn-post").forEach((b) => (b.disabled = !on));
}
async function send(who, functionName, args, value, what) {
  if (busy) return null;
  busy = true;
  setButtons(false);
  $("life").hidden = false;
  $("life-what").textContent = what;
  $("life-hash").replaceChildren();
  $("life-note").textContent = "Signing in this browser…";
  drawSteps("", false);
  $("life").scrollIntoView({ behavior: "smooth", block: "nearest" });
  // Never resent automatically: if the first send reached the node, a second
  // one would be a second transaction (a second pot, a second fee).
  let hash, err;
  try { hash = await who.client.writeContract({ address: ADDRESS, functionName, args, value: value || 0n, fees: await studioFees(who.client) }); } catch (e) { err = e; }
  if (err) {
    drawSteps("SENT", true);
    $("life-note").textContent = `The network did not confirm the send (${short(err)}). It may or may not have gone out, so this page does not resend it: press Refresh in a minute and look before trying again.`;
    busy = false;
    setButtons(true);
    return null;
  }
  $("life-hash").append(el("span", null, "Transaction: "), el("code", null, hash), el("span", null, " · "), link(`${EXPLORER_BASE}/tx/${hash}`, "view on the explorer"));
  drawSteps("SENT", false);
  const waitNote = "Posting, filing and withdrawing take under a minute; a judgement, where validators read the page, takes one to three minutes.";
  let last = "SENT", final = null;
  const t0 = Date.now();
  while (Date.now() - t0 < 8 * 60 * 1000) {
    $("life-note").textContent = `Sent ${Math.round((Date.now() - t0) / 1000)} s ago. ${waitNote}`;
    await new Promise((r) => setTimeout(r, 3000));
    let tx;
    try { tx = await reader.getTransaction({ hash }); } catch { continue; }
    const st = statusOf(tx);
    if (st && st !== last && ORDER.includes(st)) { last = st; drawSteps(st, false); }
    const noMajority = ["NO_MAJORITY", "MAJORITY_DISAGREE", "MAJORITY_TIMEOUT", "DETERMINISTIC_VIOLATION"].includes(String(tx?.resultName ?? tx?.result_name ?? "").toUpperCase());
    if ((st === "ACCEPTED" || st === "FINALIZED") && noMajority) { final = { ok: false, st: "UNDETERMINED" }; break; }
    if (st === "ACCEPTED" || st === "FINALIZED") { final = { ok: true, tx }; break; }
    if (FINAL_BAD[st]) { final = { ok: false, st }; break; }
  }
  busy = false;
  setButtons(true);
  if (!final) { $("life-note").textContent = "Not settled after eight minutes. It may still complete; press Refresh later."; return null; }
  if (!final.ok) { drawSteps(last, true); $("life-note").textContent = FINAL_BAD[final.st]; refreshBalances(); loadList(); return null; }
  const ans = leaderAnswer(final.tx);
  if (ans && ans.reverted) {
    drawSteps("REVEALING", true);
    $("life-note").textContent = `The contract refused this step: ${ans.reverted}`;
  } else if (ans && ans.ok === false) {
    drawSteps("REVEALING", true);
    $("life-note").textContent = `The contract refused this step and credited the ${gen(ans.refunded || "0")} straight back (withdraw it any time): ${ans.error}`;
  } else if (ans && functionName === "withdraw") {
    $("life-note").textContent = `Accepted: ${gen(ans.amount)} is on its way. It reaches the wallet when the transaction is finalized.`;
    followToFinal(hash);
  } else if (ans && ans.outcome) {
    const won = ans.state === "WON" ? " The bounty is won and the pot is credited." : ans.state === "PROVISIONAL" && ans.lead ? " This filing leads; a live filing that was sent earlier can still take the lead before the window ends." : "";
    $("life-note").textContent = `Accepted. Outcome ${ans.outcome}: ${OUTCOME_TEXT[ans.outcome] || ""}.${won}`;
  } else if (ans && ans.seq && functionName === "file_claim") {
    $("life-note").textContent = `Accepted. The sealed claim is filing ${ans.seq}; the chain shows only its fingerprint. ${gen(ans.burned)} was burned. Have it judged within 30 minutes: that reveals the claim.`;
  } else {
    $("life-note").textContent = "Accepted by a majority of validators.";
  }
  refreshBalances();
  await loadList();
  return ans;
}
async function followToFinal(hash) {
  const t0 = Date.now();
  while (Date.now() - t0 < 40 * 60 * 1000) {
    await new Promise((r) => setTimeout(r, 10000));
    let tx;
    try { tx = await reader.getTransaction({ hash }); } catch { continue; }
    if (statusOf(tx) === "FINALIZED") {
      if ($("life-hash").textContent.includes(hash)) drawSteps("FINALIZED", false);
      refreshBalances();
      return;
    }
  }
}

// --------------------------------------------------------------------- post

const SITE = "https://checker.brilliantnodes.com/examples/bounty";
const EXAMPLES = {
  exmFounder: { ctype: "NO_FOUNDER_REWARD", subject: "Examplecoin", tpl: `${SITE}/examplecoin/block/{n}.html`, mine: "" },
  exmMining: { ctype: "DECENTRALIZED_MINING", subject: "Examplecoin", tpl: "", mine: `${SITE}/examplecoin/mining.html` },
  ctlPremine: { ctype: "NO_PREMINE", subject: "Controlcoin", tpl: `${SITE}/controlcoin/block/{n}.html`, mine: "" },
};
const needs = (ctype) => ({ tpl: ctype !== "DECENTRALIZED_MINING", mine: ctype === "DECENTRALIZED_MINING" || ctype === "FAIR_LAUNCH" });
function syncForm() {
  const n = needs($("ctype").value);
  $("tpl").disabled = !n.tpl;
  $("mine").disabled = !n.mine;
  $("minblocks").disabled = !n.mine;
  if (!n.tpl) $("tpl").value = "";
  if (!n.mine) $("mine").value = "";
}
$("ctype").addEventListener("change", syncForm);
document.querySelectorAll("[data-example]").forEach((b) => b.addEventListener("click", () => {
  const e = EXAMPLES[b.dataset.example];
  $("ctype").value = e.ctype;
  $("subject").value = e.subject;
  $("tpl").value = e.tpl;
  $("mine").value = e.mine;
  syncForm();
}));
const postError = (m) => { $("post-error").textContent = m; $("post-error").hidden = !m; };
$("post-form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  postError("");
  const who = roles.poster;
  if (!who) return postError("Choose a poster account first, and get test GEN for it.");
  const ctype = $("ctype").value;
  const n = needs(ctype);
  const minutes = Number($("minutes").value);
  const pot = toWei($("pot").value);
  const minBlocks = n.mine ? Number($("minblocks").value) : 1000;
  // The contract's minimum is 10 minutes, counted from the transaction's own time, which is a little after this click.
  if (!Number.isInteger(minutes) || minutes < 11) return postError("A bounty posted from this page runs for at least 11 minutes.");
  if (pot === null || pot < 10n ** 16n) return postError("The pot must be at least 0.01 GEN.");
  if (!Number.isInteger(minBlocks)) return postError("Blocks needed must be a whole number from 500 to 10,000.");
  const args = [ctype, $("subject").value.trim(), n.tpl ? $("tpl").value.trim() : "", n.mine ? $("mine").value.trim() : "", nowS() + minutes * 60, minBlocks];
  await send(who, "post_bounty", args, pot, `Post a bounty of ${gen(pot)}: ${CLAIM_LABEL[ctype]} for ${args[1]}`);
});

// ------------------------------------------------------------------- render

const CLAIM_LABEL = { NO_PREMINE: "No premine", NO_FOUNDER_REWARD: "No founder reward", FAIR_LAUNCH: "Fair launch", DECENTRALIZED_MINING: "Decentralized mining" };
const STATE_LABEL = { OPEN: "Open", PROVISIONAL: "Provisional lead", WON: "Won", EXPIRED_UNCLAIMED: "Expired, unclaimed", EXPIRED: "Expired, pot returned" };
const STATE_CLASS = { OPEN: "undetermined", PROVISIONAL: "undetermined", WON: "contradicted", EXPIRED_UNCLAIMED: "supported", EXPIRED: "supported" };
const FILING_TEXT = { LIVE: "live, sealed", PAYS: "pays", NO_PAY: "no pay", SPENT: "used up", LAPSED: "ran out", OUTRANKED: "paid, but an earlier filing won" };
const filingClaim = (f) => (f.rule === "P1" ? `block ${f.height} under rule P1` : f.rule === "M1" ? "mining claim under rule M1" : "sealed claim");

function actor(sel) {
  return roles[sel.value];
}
function roleSelect(defaultRole) {
  const s = el("select", "who");
  Object.keys(roles).forEach((r) => {
    const o = el("option", null, ROLE_LABEL[r]);
    o.value = r;
    s.append(o);
  });
  s.value = defaultRole;
  s.setAttribute("aria-label", "Act as");
  return s;
}
const need = (who, what) => {
  if (who) return true;
  $("life").hidden = false;
  $("life-what").textContent = what;
  $("steps").replaceChildren();
  $("life-hash").replaceChildren();
  $("life-note").textContent = "Choose that account under Accounts first, and get test GEN for it.";
  return false;
};

function bountyCard(b) {
  const card = el("article", `check ${STATE_CLASS[b.state] || "undetermined"}`);
  const head = el("div", "check-head");
  head.append(el("span", `badge ${STATE_CLASS[b.state] || "undetermined"}`, STATE_LABEL[b.state] || b.state));
  head.append(el("span", "claim", `${CLAIM_LABEL[b.claim_type] || b.claim_type}: ${b.subject_name}`));
  head.append(el("span", "small", `#${b.id} · pot ${gen(b.pot)}`));
  card.append(head);
  card.append(el("p", "small", "The coin's name was written by the poster and is not verified."));

  const facts = el("dl", "facts");
  const add = (k, v) => { const dd = el("dd"); dd.append(v instanceof Node ? v : document.createTextNode(String(v))); facts.append(el("dt", null, k), dd); };
  add("Pinned site", b.hosts.join(", "));
  if (b.block_url_template) add("Block pages", b.block_url_template);
  if (b.mining_url) add("Mining page", link(b.mining_url, b.mining_url));
  add("Pays when", Object.values(b.pays_on).join("; or ") + (b.mining_url ? ` (min_blocks: ${b.min_blocks.toLocaleString("en")})` : ""));
  add("Filing fee", `${gen(b.fee)}, burned`);
  add("Posted by", b.poster);
  add("Takes filings until", when(b.expires_at));
  if (b.state === "OPEN" || b.state === "EXPIRED_UNCLAIMED") add("Pot can go back from", when(b.reclaim_from));
  if (b.state === "PROVISIONAL") add("Window ends", when(b.window_end));
  add("Filings", `${b.filed} (${gen(b.burned)} burned)`);
  card.append(facts);

  if (b.lead) {
    const l = b.lead, box = el("div", "lead");
    box.append(el("strong", null, b.state === "WON" ? `Won by ${shortAddr(l.hunter)} (filing ${l.seq})` : `Filing ${l.seq} by ${shortAddr(l.hunter)} leads`));
    const p = el("p", "small");
    if (l.agreed.outcome === "PAYS_P1") {
      p.append(`Agreed by the validators: block ${l.agreed.block} creates ${l.agreed.amount} coins beyond the block reward. The leader's line, found on every accepting validator's copy: `);
      p.append(el("q", null, l.leader_reading.line));
    } else {
      p.append(`Agreed by the validators: the top miner is ${l.agreed.top_miner}. Each validator's own copy of the page showed it with more than half of at least ${b.min_blocks.toLocaleString("en")} blocks. Block counts are not stored: on a live page they differ by a few blocks from one validator to the next.`);
    }
    box.append(p);
    const src = el("p", "small");
    src.append("Page read: ", link(l.url, l.url));
    box.append(src, el("p", "small", "This means the pinned page showed it. It is not a finding about the coin."));
    card.append(box);
  }

  if (b.filings.length) {
    const d = el("details");
    d.append(el("summary", null, `Filings kept (${b.filings.length})`));
    const ul = el("ul");
    b.filings.forEach((f) => ul.append(el("li", null, `Filing ${f.seq}: ${filingClaim(f)} by ${shortAddr(f.hunter)}, sent ${when(f.at)}: ${f.status === "LIVE" && !f.live ? "ran out" : FILING_TEXT[f.status] || f.status}`)));
    d.append(ul);
    card.append(d);
  }

  if (!BRADBURY && ["OPEN", "PROVISIONAL", "EXPIRED_UNCLAIMED"].includes(b.state)) card.append(actions(b));
  return card;
}

async function fileSealed(b, who, role, rule, height, what) {
  if (!need(who, "File a claim") || busy) return;
  let claim;
  try { claim = await seal(b.id, who.address, rule, height); } catch (e) { return need(null, `This browser cannot seal a claim (${short(e)})`); }
  keepSealed(who.address, b.id, claim); // kept before sending: a filing without its salt can never be judged
  await send(who, "file_claim", [b.id, claim.digest], BigInt(b.fee), `${ROLE_LABEL[role]} files a sealed claim (${what}) on bounty ${b.id}; fee ${gen(b.fee)}, burned`);
}
function judgeSealed(b, who, role) {
  if (!need(who, "Judge a filing")) return;
  const note = (m) => { $("life").hidden = false; $("life-what").textContent = "Judge a filing"; $("steps").replaceChildren(); $("life-hash").replaceChildren(); $("life-note").textContent = m; };
  const mine = b.filings.filter((f) => same(f.hunter, who.address) && f.live);
  if (!mine.length) return note("This account has no live filing on this bounty. A filing lives 30 minutes.");
  const kept = sealedList(who.address, b.id);
  const claim = mine.map((f) => kept.find((k) => k.digest === f.digest)).find(Boolean);
  if (!claim) return note("This browser does not hold the rule, block and salt of that filing. It was filed from somewhere else, or the browser's storage was cleared.");
  send(who, "judge", [b.id, claim.rule, claim.height, claim.salt], 0n, `${ROLE_LABEL[role]} reveals its claim on bounty ${b.id} (${claim.rule === "P1" ? "block " + claim.height : "mining"}) and has it judged`);
}

function actions(b) {
  const box = el("div", "acts");
  const rules = Object.keys(b.pays_on);
  const row = (...nodes) => { const r = el("div", "act"); r.append(...nodes); box.append(r); return r; };
  const btn = (label, fn) => { const x = el("button", "secondary", label); x.type = "button"; x.addEventListener("click", fn); return x; };
  if (b.state === "OPEN") {
    const who = roleSelect("hunter");
    const nodes = [el("span", "small", "File as"), who];
    if (rules.includes("P1")) {
      const h = el("input", "height");
      h.inputMode = "numeric";
      h.value = "1";
      h.setAttribute("aria-label", "Block number, 0 to 100");
      nodes.push(el("span", "small", "block"), h, btn(`File block claim (${gen(b.fee)})`, () => {
        const n = Number(h.value);
        if (!Number.isInteger(n) || n < 0 || n > 100) { h.focus(); return; }
        fileSealed(b, actor(who), who.value, "P1", n, `block ${n}`);
      }));
    }
    if (rules.includes("M1")) nodes.push(btn(`File mining claim (${gen(b.fee)})`, () => fileSealed(b, actor(who), who.value, "M1", 0, "mining")));
    row(...nodes);
  }
  if (b.state !== "EXPIRED_UNCLAIMED" || b.filings.some((f) => f.live)) {
    const who = roleSelect("hunter");
    row(el("span", "small", "Reveal and judge the live filing of"), who, btn("Judge", () => judgeSealed(b, actor(who), who.value)));
  }
  if (b.state === "PROVISIONAL") {
    const who = roleSelect("second");
    row(el("span", "small", "Anyone may finalize once the window has ended:"), who, btn("Finalize", () => {
      if (need(actor(who), "Finalize")) send(actor(who), "finalize", [b.id], 0n, `${ROLE_LABEL[who.value]} finalizes bounty ${b.id}`);
    }));
  }
  if (b.state === "EXPIRED_UNCLAIMED") {
    row(el("span", "small", `The poster can take the pot back from ${when(b.reclaim_from)}:`), btn("Reclaim as Poster", () => {
      if (need(roles.poster, "Reclaim")) send(roles.poster, "reclaim", [b.id], 0n, `Poster reclaims the pot of bounty ${b.id}`);
    }));
  }
  return box;
}

async function loadList() {
  if (!ADDRESS) {
    $("list-state").textContent = `The bounties contract is not deployed on ${NET.label} yet.`;
    return;
  }
  try {
    const list = await read("get_latest", [20, nowS()]);
    const box = $("list");
    box.replaceChildren();
    $("list-state").textContent = list.length ? `${list.length} most recent, newest first, as of ${when(nowS())}.` : "No bounties yet.";
    list.forEach((b) => box.append(bountyCard(b)));
    if (busy) setButtons(false);
  } catch (e) {
    $("list-state").textContent = `The contract could not be read: ${short(e)}`;
  }
  loadTotals();
}
$("refresh").addEventListener("click", () => { loadList(); refreshBalances(); });

async function loadTotals() {
  try {
    const t = await read("totals");
    let line = `Held as pots: ${gen(t.locked)}. Credited and not yet withdrawn: ${gen(t.credited)}. Burned filing fees: ${gen(t.burned)}. Sum: ${gen(t.accounted_for)}.`;
    try {
      const bal = await reader.getBalance({ address: ADDRESS });
      line += ` The contract's balance on chain: ${gen(bal)}${String(bal) === t.accounted_for ? " (equal)" : " (not equal right now: a transaction is on its way, or GEN was sent to the contract outside these calls)"}.`;
    } catch {}
    $("totals").textContent = line;
  } catch {}
}
async function loadRules() {
  if (!ADDRESS) return;
  try {
    const r = await read("get_rules");
    const rows = [
      ["Rule P1 pays when", r.pay_condition.P1],
      ["Rule M1 pays when", r.pay_condition.M1],
      ["Filing fee", `${r.fee_bp / 100}% of the pot, at least ${gen(r.min_fee_wei)}; it goes to ${r.fee_goes_to}`],
      ["A filing can be judged for", `${r.filing_ttl_seconds / 60} minutes`],
      ["The pot can go back", `${(r.filing_ttl_seconds + r.process_margin_seconds) / 60} minutes after the expiry`],
      ["Smallest pot", gen(r.min_bounty_wei)],
      ["Blocks needed for the mining rule", `${r.min_blocks_floor.toLocaleString("en")} to ${r.min_blocks_cap.toLocaleString("en")}`],
      ["A filing seals", r.digest],
      ["The queue", r.queue],
      ["Rows with one of these words are not one miner", r.catch_all_words.join(", ")],
      ["Text read from a page", `First ${r.page_chars.toLocaleString("en")} characters`],
      ["An unreadable or wrong page", `Leaves the filing live ${r.soft_tries} times`],
    ];
    const t = $("rules");
    t.replaceChildren();
    rows.forEach(([a, b]) => { const tr = el("tr"); tr.append(el("th", null, a), el("td", null, b)); t.append(tr); });
  } catch {}
}

// --------------------------------------------------------------------- boot

const net = $("net");
net.append(el("span", "dot"));
Object.values(NETWORKS).forEach((n) => {
  if (n.key === NET.key) {
    const cur = el("strong", null, n.label);
    cur.setAttribute("aria-current", "true");
    net.append(cur);
  } else {
    const a = el("a", null, n.label);
    a.href = `?net=${n.key}`;
    a.title = `Switch to ${n.name}`;
    net.append(a);
  }
});
$("back").href = `./?net=${NET.key}`;
if (BRADBURY) {
  $("accounts-card").hidden = true;
  $("post-card").hidden = true;
  const b = $("net-banner");
  b.hidden = false;
  b.replaceChildren(
    el("strong", null, "Testnet Bradbury Phase 2. "),
    el("span", null, "GenLayer's public testnet, where validators use real models and real web access. This view shows the bounties decided there. It only reads, so it needs no wallet. "),
    Object.assign(el("a", null, "Try it free on Studio"), { href: "?net=studio" }),
  );
} else {
  Object.keys(roles).forEach((r) => { if (store.get(`lcb.temp.${r}`)) tempAccount(r); });
}
const fc = $("foot-contract");
if (ADDRESS) {
  fc.append(el("span", null, "Bounties contract: "), link(`${EXPLORER_BASE}/address/${ADDRESS}`, ADDRESS));
}
$("foot-repo").href = REPO_URL;
syncForm();
loadList();
loadRules();
