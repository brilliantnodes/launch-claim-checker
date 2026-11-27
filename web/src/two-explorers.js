import { createClient, createAccount, generatePrivateKey, abi } from "genlayer-js";
import { studionet } from "genlayer-js/chains";
// Since late November 2026 GenLayer Studio refuses a transaction without a fee distribution.
// Reads stay on genlayer-js 1; every write goes through genlayer-js 2 with a fee estimate
// (about 0.1 test GEN deposited, the unused part refunded).
import { createClient as createWriter, createAccount as createAccountW } from "genlayer-js-studio";
import { studionet as studionetW } from "genlayer-js-studio/chains";
const studioFees = async (w) => { const f = await w.estimateTransactionFees(); return { distribution: f.distribution, feeValue: f.feeValue }; };
import { NET, NETWORKS, EXPLORER_BASE, REPO_URL } from "./config.js";

// Launch Claim Checker v2 (contracts/launch_claim_checker_v2.py). On Studio the page
// checks, bonds, challenges, re-checks, settles, collects and withdraws with temporary
// accounts. The Bradbury view only reads the record there, so it needs no wallet.
const BRADBURY = NET.key === "bradbury";
const ADDRESS = NET.checkerV2 || "";
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
  if (/^https?:\/\//i.test(href)) { // only http(s) links are ever made clickable
    a.href = href;
    a.target = "_blank";
    a.rel = "noopener noreferrer nofollow";
  }
  return a;
};
const RPC = studionet.rpcUrls.default.http[0];
const reader = BRADBURY ? v2.createClient({ chain: v2chains.testnetBradbury, endpoint: NET.checkerV2Rpc || NET.rpc }) : createClient({ chain: studionet });

function plain(v) {
  if (v instanceof Map) return Object.fromEntries([...v.entries()].map(([k, x]) => [k, plain(x)]));
  if (Array.isArray(v)) return v.map(plain);
  if (typeof v === "bigint") return Number(v) > Number.MAX_SAFE_INTEGER ? v.toString() : Number(v);
  if (v && typeof v === "object") return Object.fromEntries(Object.entries(v).map(([k, x]) => [k, plain(x)]));
  return v;
}
// Reads go one at a time, and a "rate limit" answer (the Bradbury Phase 3 public node limits gen_call) is asked again.
let readQueue = Promise.resolve();
const readOnce = async (functionName, args) => {
  for (let i = 0; ; i++) {
    try {
      return plain(await reader.readContract({ address: ADDRESS, functionName, args }));
    } catch (e) {
      if (i >= 5 || !/rate limit/i.test(String(e?.message || e))) throw e;
      await new Promise((r) => setTimeout(r, 1500 * (i + 1)));
    }
  }
};
const read = (functionName, args = []) => {
  const p = readQueue.then(() => readOnce(functionName, args));
  readQueue = p.catch(() => {});
  return p;
};
const short = (e) => String((e && (e.shortMessage || e.message)) || e).slice(0, 300);
const shortAddr = (a) => (a ? `${a.slice(0, 6)}…${a.slice(-4)}` : "");
const same = (a, b) => !!a && !!b && String(a).toLowerCase() === String(b).toLowerCase();
const nowS = () => Math.floor(Date.now() / 1000);
const when = (s) => (s ? new Date(s * 1000).toISOString().replace("T", " ").slice(11, 16) + " UTC" : "");
const inMin = (s) => { const d = s - nowS(); return d <= 0 ? "passed" : d < 90 ? `in ${d} s` : `in ${Math.round(d / 60)} min`; };
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

// ----------------------------------------------------------------- accounts

const ROLE_LABEL = { requester: "Requester", challenger1: "Challenger", challenger2: "Second challenger" };
const roles = { requester: null, challenger1: null, challenger2: null };
const store = {
  get: (k) => { try { return localStorage.getItem(k); } catch { return null; } },
  set: (k, v) => { try { localStorage.setItem(k, v); } catch {} },
};
function tempAccount(role) {
  let key = store.get(`lcc2.temp.${role}`);
  if (!key) {
    key = generatePrivateKey();
    store.set(`lcc2.temp.${role}`, key);
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
  ["PROPOSING", "Leader works", "One validator runs the step; for a check or a re-check it reads both pages now."],
  ["COMMITTING", "Validators check", "The others run it on their own, reading the pages themselves, and vote."],
  ["REVEALING", "Votes revealed", "Votes are opened and counted."],
  ["ACCEPTED", "Accepted", "A majority agreed; the new state is recorded and any money is credited."],
  ["FINALIZED", "Finalized", "The appeal window has passed. A withdrawal's GEN reaches the wallet now."],
];
const ORDER = STEPS.map((s) => s[0]);
const FINAL_BAD = {
  UNDETERMINED: "The validators did not agree, so nothing changed and nothing was recorded. It can be sent again.",
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
    if (p && Array.isArray(p.raw)) { const v = plain(abi.calldata.decode(new Uint8Array(p.raw))); return v && typeof v === "object" ? v : null; }
    return null;
  } catch { return null; }
}

let busy = false;
const setButtons = (on) => document.querySelectorAll("#list button, #btn-check").forEach((b) => (b.disabled = !on));
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
  // Never resent automatically: if the first send reached the node, a second one would be a second transaction.
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
  const waitNote = "A bond, a challenge or a withdrawal takes under a minute; a check or a re-check, where every validator reads both pages, takes one to three minutes.";
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
  } else if (ans && functionName === "check_claim") {
    $("life-note").textContent = `Accepted. Check ${ans.id}: ${ans.verdict} (${ans.rule}).`;
  } else if (ans && functionName === "bond") {
    $("life-note").textContent = `Accepted. ${gen(ans.bonded)} bonded. Challenges are taken until ${when(ans.close)}.`;
  } else if (ans && functionName === "challenge") {
    $("life-note").textContent = `Accepted. Challenger ${ans.challenger}. A re-check can be sent from ${when(ans.recheck_from)}.`;
  } else if (ans && functionName === "recheck") {
    $("life-note").textContent = ans.decided ? `Accepted. The re-check found ${ans.verdict} (${ans.rule}): the bond is ${STATE_LABEL[ans.state] || ans.state}.${ans.state === "OVERTURNED" ? " Half the bond is burned; the challengers share the rest." : ""}` : `Accepted, but nothing was decided: ${ans.why}.`;
  } else if (ans && functionName === "settle") {
    $("life-note").textContent = `Accepted. The bond is ${STATE_LABEL[ans.state] || ans.state}.`;
  } else if (ans && functionName === "collect") {
    $("life-note").textContent = BigInt(ans.credited || "0") > 0n ? `Accepted. ${gen(ans.credited)} credited; withdraw it under Accounts.` : `Accepted. This outcome (${STATE_LABEL[ans.state] || ans.state}) gives this account nothing.`;
  } else if (ans && functionName === "withdraw") {
    $("life-note").textContent = `Accepted: ${gen(ans.amount)} is on its way. It reaches the wallet when the transaction is finalized.`;
  } else {
    $("life-note").textContent = "Accepted by a majority of validators.";
  }
  refreshBalances();
  await loadList();
  return ans;
}

// -------------------------------------------------------------------- check

const A = "https://checker.brilliantnodes.com/v2";
const B = "https://brilliantnodes.github.io/demo-explorer";
const EXAMPLES = {
  exm: { ctype: "NO_FOUNDER_REWARD", coin: "Examplecoin", a: `${A}/examplecoin-block-1.html`, b: `${B}/examplecoin/block-1.html`, text: "No founder reward" },
  ctl: { ctype: "NO_PREMINE", coin: "Controlcoin", a: `${A}/controlcoin-block-1.html`, b: `${B}/controlcoin/block-1.html`, text: "No premine" },
  spl: { ctype: "NO_FOUNDER_REWARD", coin: "Splitcoin", a: `${A}/splitcoin-block-1.html`, b: `${B}/splitcoin/block-1.html`, text: "" },
  mine: { ctype: "DECENTRALIZED_MINING", coin: "Examplecoin", a: `${A}/examplecoin-mining.html`, b: `${B}/examplecoin/pools.html`, text: "" },
};
document.querySelectorAll("[data-example]").forEach((b) => b.addEventListener("click", () => {
  const e = EXAMPLES[b.dataset.example];
  $("ctype").value = e.ctype;
  $("coin").value = e.coin;
  $("url-a").value = e.a;
  $("url-b").value = e.b;
  $("ctext").value = e.text;
}));
const checkError = (m) => { $("check-error").textContent = m; $("check-error").hidden = !m; };
const host = (u) => { try { return new URL(u).hostname; } catch { return ""; } };
// The contract's domain rule: the last two labels of a host, three for names such as co.uk; all *.github.io are one domain.
const SECOND_LEVEL = ["co", "com", "net", "org", "gov", "edu", "ac"];
const domainOf = (h) => { const l = h.split("."); return l.length >= 3 && l[l.length - 1].length === 2 && SECOND_LEVEL.includes(l[l.length - 2]) ? l.slice(-3).join(".") : l.slice(-2).join("."); };
$("check-form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  checkError("");
  const who = roles.requester;
  if (!who) return checkError("Choose a requester account first, and get test GEN for it.");
  const a = $("url-a").value.trim(), b = $("url-b").value.trim(), coin = $("coin").value.trim();
  if (!/^https:\/\//i.test(a) || !/^https:\/\//i.test(b)) return checkError("Both explorer addresses must start with https://.");
  if (domainOf(host(a)) === domainOf(host(b))) return checkError(`The two explorers must be on different domains (both are on ${domainOf(host(a))}).`);
  if (coin.length < 4) return checkError("Name the coin (4 to 40 characters), as both pages write it.");
  await send(who, "check_claim", [a, b, coin, $("ctype").value, $("ctext").value.trim()], 0n, `Check "${CLAIM_LABEL[$("ctype").value]}" for ${coin} on ${host(a)} and ${host(b)}`);
});

// ------------------------------------------------------------------- render

const CLAIM_LABEL = { NO_PREMINE: "No premine", NO_FOUNDER_REWARD: "No founder reward", FAIR_LAUNCH: "Fair launch", DECENTRALIZED_MINING: "Decentralized mining" };
const VERDICT_CLASS = { SUPPORTED: "supported", CONTRADICTED: "contradicted", UNDETERMINED: "undetermined" };
const STATE_LABEL = { NONE: "no bond", BONDED: "bonded", UPHELD: "upheld", OVERTURNED: "overturned", NOT_CONFIRMED: "not confirmed", RELEASED: "released" };
const RULE_TEXT = {
  "BOTH:P1": "both explorers show the same extra allocation in the same early block (0 to 100)",
  "BOTH:P2": "both explorers show block 0 or 1 with only the miner reward",
  "BOTH:M1": "on both explorers the same miner has more than half of the blocks",
  "BOTH:M2": "on both explorers the largest miner has a third of the blocks or less",
  D1_EXPLORERS_DISAGREE: "the two explorers do not show the same thing",
  W1_WRONG_PAGE: "a page does not name the coin near the top",
  D2_NOT_SHOWN_BY_BOTH: "the rule needs both explorers to show it; one does not",
  U1_NOT_ENOUGH_EVIDENCE: "the pages do not show enough to decide",
};
const CLS_TEXT = { SUPPORTS: "supports the claim", CONTRADICTS: "contradicts the claim", WRONG_PAGE: "wrong page", UNCLEAR: "unclear" };
let rules = null;
const typedBond = new Map(); // bond amounts typed on the page survive the list's refresh

function pageLine(label, url, p) {
  const li = el("li");
  li.append(el("strong", null, `${label}: `), link(url, host(url) || url), document.createTextNode(` · ${CLS_TEXT[p?.cls] || p?.cls || "not read"}${p?.rule ? ` (${p.rule})` : ""}`));
  if (p?.amount_text) li.append(document.createTextNode(` · block ${p.height}: ${p.amount_text}`));
  else if (p?.height !== undefined && p?.rule === "P2") li.append(document.createTextNode(` · block ${p.height}`));
  if (p?.miner) li.append(document.createTextNode(` · top miner ${p.miner}`));
  if (p?.quote) { li.append(el("br")); li.append(el("q", null, p.quote)); }
  return li;
}

function act(label, role, fn, value, what, c) {
  const b = el("button", "secondary", label);
  b.type = "button";
  b.addEventListener("click", () => {
    const who = roles[role];
    if (!who) { $("life").hidden = false; $("life-what").textContent = what; $("steps").replaceChildren(); $("life-hash").replaceChildren(); $("life-note").textContent = `Choose a ${ROLE_LABEL[role].toLowerCase()} account under Accounts first, and get test GEN for it.`; return; }
    send(who, fn, [c.id], value, what);
  });
  return b;
}

function checkCard(c, challengers) {
  const r = c.result, bd = c.bond, t = c.times || {};
  const card = el("article", `check ${VERDICT_CLASS[r.verdict] || "undetermined"}`);
  const head = el("div", "check-head");
  head.append(el("span", `badge ${VERDICT_CLASS[r.verdict] || "undetermined"}`, r.verdict));
  head.append(el("span", "claim", `${CLAIM_LABEL[c.claim_type] || c.claim_type}: ${c.coin_name}`));
  head.append(el("span", "small", `#${c.id} · ${r.rule}${bd.state !== "NONE" ? ` · bond ${STATE_LABEL[bd.state] || bd.state}` : ""}`));
  card.append(head);
  card.append(el("p", "small", `${RULE_TEXT[r.rule] || r.rule}. This is what the two pages showed, not a finding about the coin.`));
  const ul = el("ul", "pages");
  ul.append(pageLine("Explorer A", c.explorer_a_url, r.a), pageLine("Explorer B", c.explorer_b_url, r.b));
  card.append(ul);

  const facts = el("dl", "facts");
  const add = (k, v) => { const dd = el("dd"); dd.append(v instanceof Node ? v : document.createTextNode(String(v))); facts.append(el("dt", null, k), dd); };
  add("Requested by", c.requester);
  add("Checked at", when(c.t0));
  if (bd.state !== "NONE") {
    add("Bond", `${gen(bd.amount)} · held now ${gen(bd.held)}`);
    add("Challengers", challengers.length ? challengers.map(shortAddr).join(", ") : "none");
    add("Challenges until", `${when(t.close)} (${inMin(t.close)})`);
    if (bd.n > 0) add("Re-check window", `${when(t.rc_open)} to ${when(t.rc_end)}`);
    if (bd.recheck) add("Re-check found", `${bd.recheck.verdict} (${bd.recheck.rule}) at ${when(bd.recheck.at)}`);
    if (bd.burned) add("Burned", `${gen(bd.burned)} (half the bond, out of everyone's reach)`);
  }
  card.append(facts);
  if (bd.recheck) {
    const ul2 = el("ul", "pages");
    ul2.append(pageLine("Re-check, explorer A", c.explorer_a_url, bd.recheck.a), pageLine("Re-check, explorer B", c.explorer_b_url, bd.recheck.b));
    card.append(ul2);
  }
  if (BRADBURY) return card;

  const box = el("div", "acts"), now = nowS();
  // as the contract: block 0 or 1 on both pages, and a BOTH:P1 verdict only when both pages also show the block's ordinary reward
  const bondable = (rules?.bondable || ["BOTH:P1", "BOTH:P2"]).includes(r.rule) && (rules?.bondable_claims || ["NO_PREMINE", "NO_FOUNDER_REWARD"]).includes(c.claim_type)
    && [r.a, r.b].every((p) => Number(p?.height ?? 2) <= 1) && (r.rule !== "BOTH:P1" || [r.a, r.b].every((p) => p?.reward_text));
  const mine = roles.requester && same(roles.requester.address, c.requester);
  const bondWin = Number(rules?.windows_seconds?.bond_win || 600);
  const min = BigInt(rules?.min_bond_wei || "10000000000000000");
  if (bd.state === "NONE" && bondable && mine && now < c.t0 + bondWin) {
    const row = el("div", "act");
    const amt = el("input", "height"); amt.value = typedBond.get(c.id) || "1"; amt.setAttribute("aria-label", "Bond in test GEN"); amt.style.width = "5rem";
    amt.addEventListener("input", () => typedBond.set(c.id, amt.value));
    const b = el("button", "secondary", "Bond as Requester");
    b.type = "button";
    b.addEventListener("click", () => {
      const v = toWei(amt.value);
      if (v === null || v < min) { $("life").hidden = false; $("life-note").textContent = `A bond is at least ${gen(min)}.`; return; }
      if (!roles.requester) { $("life").hidden = false; $("life-note").textContent = "Choose a requester account first."; return; }
      send(roles.requester, "bond", [c.id], v, `Requester bonds ${gen(v)} on check ${c.id}`);
    });
    row.append(amt, el("span", "small", "test GEN"), b, el("span", "small", `until ${when(c.t0 + bondWin)}`));
    box.append(row);
  }
  if (bd.state === "BONDED" && !bd.recheck) {
    const row = el("div", "act");
    if (now <= t.close) {
      for (const [role, label] of [["challenger1", "Challenger"], ["challenger2", "Second challenger"]]) {
        const who = roles[role];
        if (who && (same(who.address, c.requester) || challengers.some((x) => same(x, who.address)))) continue; // cannot challenge
        row.append(act(`Challenge as ${label}`, role, "challenge", BigInt(bd.amount), `${label} deposits ${gen(bd.amount)} against check ${c.id}`, c));
      }
    }
    if (bd.n > 0 && now >= t.rc_open && now <= t.rc_end) row.append(act("Re-check now", "challenger1", "recheck", 0n, `Re-check check ${c.id}: every validator reads both pages again`, c));
    if ((bd.n === 0 && now >= t.rc_open) || (bd.n > 0 && now >= t.nc_from)) row.append(act("Settle", "challenger1", "settle", 0n, `Settle the bond on check ${c.id}`, c));
    if (!row.childNodes.length) row.append(el("span", "small", now < t.rc_open ? `Next: ${bd.n > 0 ? "re-check" : "release"} from ${when(t.rc_open)} (${inMin(t.rc_open)}).` : `Next: settle from ${when(t.nc_from)} (${inMin(t.nc_from)}).`));
    box.append(row);
  }
  if (["UPHELD", "OVERTURNED", "NOT_CONFIRMED", "RELEASED"].includes(bd.state)) {
    const row = el("div", "act");
    for (const role of Object.keys(roles)) {
      const who = roles[role];
      const isReq = who && same(who.address, c.requester);
      if (who && ((isReq && !bd.req_collected) || (!isReq && challengers.some((x) => same(x, who.address))))) row.append(act(`Collect as ${ROLE_LABEL[role]}`, role, "collect", 0n, `${ROLE_LABEL[role]} collects what check ${c.id} gives it`, c));
    }
    if (row.childNodes.length) box.append(row);
  }
  if (box.childNodes.length) card.append(box);
  return card;
}

async function loadList() {
  if (!ADDRESS) { $("list-state").textContent = "No v2 contract is set for this network yet."; return; }
  $("list-state").textContent = "Loading…";
  try {
    const list = await read("get_latest", [10, nowS()]);
    const challengers = await Promise.all(list.map((c) => (c.bond.state !== "NONE" ? read("get_challengers", [c.id]).catch(() => []) : [])));
    $("list").replaceChildren(...list.map((c, i) => checkCard(c, challengers[i])));
    $("list-state").textContent = list.length ? (list.length === 1 ? "The latest check. Times are shown in UTC." : `The ${list.length} latest checks. Times are shown in UTC.`) : "No checks yet.";
  } catch (e) {
    $("list-state").textContent = `Could not read the contract: ${short(e)}`;
  }
}
$("refresh").addEventListener("click", () => { loadList(); refreshBalances(); });

async function loadRules() {
  if (!ADDRESS) return;
  try {
    rules = await read("get_rules");
    const w = rules.windows_seconds, m = (s) => `${Math.round(s / 60)} min`;
    $("windows-line").textContent = `On this contract: ${m(w.bond_win)} to bond after a check, ${m(w.ch_win)} to challenge, then ${m(w.grace)} of grace, ${m(w.rc_win)} to re-check and ${m(w.grace)} more before a challenged bond can be settled as not confirmed. Minimum bond ${gen(rules.min_bond_wei)}.`;
    const rows = [
      ["Bondable verdicts", `${rules.bondable.join(", ")} on block 0 or 1; BOTH:P1 only when both pages also show the block's ordinary reward (not zero)`],
      ["Claims", rules.claim_types.join(", ")],
      ["Bondable claims", (rules.bondable_claims || []).join(", ")],
      ["Upheld", `${rules.upheld || "the same fact again"}: the requester gets the bond back plus every challenger's deposit`],
      ["Overturned", `the opposite rule about the same block on both explorers: ${rules.overturned || "half the bond is burned; each challenger gets its deposit back and an equal share of the rest"}`],
      ["Not confirmed", "everyone gets back what they put in"],
      ["Released", "no challenger: the requester gets the bond back"],
      ["P1, extra allocation", `an output in blocks 0 to ${rules.max_height} beyond the block reward, printed on the page`],
      ["M1, one miner", rules.m1],
      ["M2, spread out", rules.m2],
      ["Page read", `the first ${rules.page_chars.toLocaleString("en")} characters`],
    ];
    $("rules").replaceChildren(...rows.map(([k, v]) => { const tr = el("tr"); tr.append(el("th", null, k), el("td", null, v)); return tr; }));
    const t = await read("totals");
    $("totals").textContent = `${t.checks} ${Number(t.checks) === 1 ? "check" : "checks"} so far. Locked in bonds and challenges: ${gen(t.locked)}. Credited, waiting to be withdrawn: ${gen(t.credited)}. Burned: ${gen(t.burned || "0")}.`;
  } catch (e) {
    $("totals").textContent = `Could not read the rules: ${short(e)}`;
  }
}

// --------------------------------------------------------------- networks

function netSwitch() {
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
      a.title = n.key === "bradbury" ? "Switch to GenLayer Testnet Bradbury (version 2 is on Phase 3)" : `Switch to ${n.name}`;
      net.append(a);
    }
  });
  if (ADDRESS) $("foot-contract").append(el("span", null, "v2 contract: "), link(`${EXPLORER_BASE}/address/${ADDRESS}`, ADDRESS));
  $("foot-repo").href = REPO_URL;
  if (BRADBURY) {
    $("accounts-card").hidden = true;
    $("check-card").hidden = true;
    const b = $("net-banner");
    b.hidden = false;
    b.replaceChildren(
      el("strong", null, "Testnet Bradbury Phase 3. "),
      el("span", null, "GenLayer's public testnet, where validators use real models and real web access. This view shows the checks and bonds decided there. It only reads, so it needs no wallet. "),
      Object.assign(el("a", null, "Try it free on Studio"), { href: "?net=studio" }),
    );
  } else {
    Object.keys(roles).forEach((r) => { if (store.get(`lcc2.temp.${r}`)) tempAccount(r); });
  }
}

netSwitch();
loadRules();
loadList();
setInterval(() => { if (!busy) loadList(); }, 60000);
