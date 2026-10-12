/*
 * open.js: the coin-flip page.
 *
 * Flow:
 *   1. load()   asks the server for the coins in the open roll (JSON).
 *   2. show()   puts the current coin face-down.
 *   3. flip()   turns it over (adds the CSS class "flipped").
 *   4. decide("keep" | "return") tells the server, then moves to the next coin.
 *
 * fetch() is the browser's built-in way to call a URL from JavaScript.
 * "async/await" just means "wait for the server's answer before continuing".
 */

let coins = [];      // array of coin objects from /api/pending
let index = 0;       // which coin we're on
let flipped = false;
let keptCount = 0, returnedCount = 0;

// Short helper so we don't type document.getElementById everywhere
const $ = (id) => document.getElementById(id);

async function load() {
  const response = await fetch("/api/pending");
  coins = await response.json();
  index = 0;
  show();
}

function show() {
  if (index >= coins.length) {              // no coins left: show summary
    $("coin").parentElement.hidden = true;
    $("done").hidden = false;
    $("summary").textContent = coins.length === 0
      ? "No open roll. Go to the Store to open one."
      : `Kept ${keptCount}, returned ${returnedCount}.`;
    return;
  }
  const c = coins[index];
  flipped = false;
  $("coin").classList.remove("flipped", "special");
  $("progress").textContent = `Coin ${index + 1} of ${coins.length}`;
  // Fill the (still hidden) front face
  $("coin-title").textContent = c.title;
  $("coin-grade").textContent = `${c.est_label} (your estimate)`;
  $("coin-badges").innerHTML = c.badges.map(b => `<span class="badge">${b}</span>`).join("");
  $("btn-flip").disabled = false;
  $("btn-keep").disabled = true;
  $("btn-return").disabled = true;
}

function flip() {
  if (flipped || index >= coins.length) return;
  flipped = true;
  $("coin").classList.add("flipped");
  if (coins[index].special || coins[index].badges.length) $("coin").classList.add("special");
  $("btn-flip").disabled = true;
  $("btn-keep").disabled = false;
  $("btn-return").disabled = false;
}

async function decide(action) {
  if (!flipped) return;
  const c = coins[index];
  const response = await fetch(`/api/coin/${c.id}/${action}`, { method: "POST" });
  const result = await response.json();
  if (!response.ok) { alert(result.error); return; }

  $("balance").textContent = result.balance;   // update wallet in the header
  if (action === "keep") keptCount++; else returnedCount++;

  // Add a line to the log under the coin
  const li = document.createElement("li");
  li.textContent = `${c.title} ${c.est_label} → ${result.placed}`;
  li.className = result.placed;
  $("log").appendChild(li);

  index++;
  show();
}

async function returnRest() {
  if (!confirm("Return every remaining coin in this roll to the bank?")) return;
  const response = await fetch("/api/return-rest", { method: "POST" });
  const result = await response.json();
  $("balance").textContent = result.balance;
  returnedCount += coins.length - index;
  index = coins.length;
  show();
}

// Wire up buttons
$("btn-flip").onclick = flip;
$("btn-keep").onclick = () => decide("keep");
$("btn-return").onclick = () => decide("return");
$("btn-return-rest").onclick = returnRest;

// Keyboard shortcuts: Space = flip, K = keep, R = return
document.addEventListener("keydown", (e) => {
  if (e.code === "Space") { e.preventDefault(); flip(); }
  if (e.key === "k" || e.key === "K") decide("keep");
  if (e.key === "r" || e.key === "R") decide("return");
});

load();
