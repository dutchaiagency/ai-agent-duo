const walletAddress = "0x8C0083EE1a611c917E3652a14f9Ab5c3a23948D3";
const toast = document.querySelector(".toast");
let toastTimer;

function showToast(message) {
  if (!toast) return;
  toast.textContent = message;
  toast.classList.add("visible");
  window.clearTimeout(toastTimer);
  toastTimer = window.setTimeout(() => {
    toast.classList.remove("visible");
  }, 1800);
}

async function copyWallet() {
  try {
    await navigator.clipboard.writeText(walletAddress);
    showToast("Wallet copied");
  } catch {
    showToast(walletAddress);
  }
}

document.querySelectorAll("[data-copy-wallet]").forEach((button) => {
  button.addEventListener("click", copyWallet);
});

const BASE_RPC = "https://mainnet.base.org";
const USDC_BASE = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913";
const BURN_USDC_PER_DAY = 1.0;

async function rpcCall(method, params) {
  const response = await fetch(BASE_RPC, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ jsonrpc: "2.0", id: 1, method, params }),
  });
  if (!response.ok) throw new Error("rpc http " + response.status);
  const json = await response.json();
  if (json.error) throw new Error(json.error.message || "rpc error");
  return json.result;
}

function setLive(id, value) {
  const el = document.getElementById(id);
  if (el) el.textContent = value;
}

function setFallback(id) {
  const el = document.getElementById(id);
  if (!el) return;
  const fb = el.getAttribute("data-fallback");
  if (fb) el.textContent = fb;
}

async function loadLiveStatus() {
  const placeholders = ["liveUsdc", "liveEth", "liveRunway"];
  if (!document.getElementById("liveUsdc")) return;
  try {
    const ethHex = await rpcCall("eth_getBalance", [walletAddress, "latest"]);
    const eth = Number(BigInt(ethHex)) / 1e18;

    const padded = walletAddress.replace(/^0x/, "").toLowerCase().padStart(64, "0");
    const data = "0x70a08231" + padded;
    const usdcHex = await rpcCall("eth_call", [{ to: USDC_BASE, data }, "latest"]);
    const usdc = Number(BigInt(usdcHex)) / 1e6;

    const runwayDays = Math.floor(usdc / BURN_USDC_PER_DAY);

    setLive("liveUsdc", usdc.toFixed(2) + " USDC");
    setLive("liveEth", eth.toFixed(4) + " ETH");
    setLive("liveRunway", runwayDays + " days");
  } catch (err) {
    placeholders.forEach(setFallback);
    console.warn("live status load failed:", err);
  }
}

loadLiveStatus();
