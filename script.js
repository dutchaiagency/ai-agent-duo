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
const BURN_USDC_PER_DAY = 1.5;

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

// Funnel instrumentation: log every click on a tracked CTA so we can measure
// which source/section actually drives intake briefs. No backend; events are
// kept in localStorage and the user-source is appended to outbound links so
// the GitHub issue / mailto referrer carries the funnel step.
const FUNNEL_KEY = "ad_funnel_events_v1";
const FUNNEL_MAX = 200;

function getFunnelEvents() {
  try {
    return JSON.parse(localStorage.getItem(FUNNEL_KEY) || "[]");
  } catch {
    return [];
  }
}

function recordFunnelEvent(event) {
  try {
    const events = getFunnelEvents();
    events.push(event);
    while (events.length > FUNNEL_MAX) events.shift();
    localStorage.setItem(FUNNEL_KEY, JSON.stringify(events));
  } catch {
    // storage disabled; ignore
  }
}

// Inbound attribution: if a visitor arrives with ?source=... or ?ref=... we
// propagate that to outbound CTAs so the GitHub issue form prefills its
// "source" field with the original referrer (e.g. "devto-longform-2026-04-30")
// instead of the per-CTA default ("site-hero", "site-contact"...).
function getInboundSource() {
  try {
    const params = new URLSearchParams(window.location.search);
    return params.get("source") || params.get("ref") || null;
  } catch {
    return null;
  }
}

function annotateOutbound(href, step) {
  try {
    const url = new URL(href, window.location.href);
    if (url.origin === window.location.origin && href.startsWith("#")) return href;
    if (!url.searchParams.has("utm_source")) {
      url.searchParams.set("utm_source", "ai-agent-duo");
    }
    if (!url.searchParams.has("utm_medium")) {
      url.searchParams.set("utm_medium", "site");
    }
    if (!url.searchParams.has("utm_campaign")) {
      url.searchParams.set("utm_campaign", "intake");
    }
    if (step && !url.searchParams.has("utm_content")) {
      url.searchParams.set("utm_content", step);
    }
    const inbound = getInboundSource();
    if (inbound) {
      // Override per-CTA default so the issue's source field reflects where
      // the visitor actually came from before landing on the site.
      url.searchParams.set("source", inbound);
    }
    return url.toString();
  } catch {
    return href;
  }
}

function inferStep(el) {
  if (el.dataset.funnelStep) return el.dataset.funnelStep;
  const section = el.closest("section");
  const sectionId = section ? section.id || section.className.split(" ")[0] : "global";
  const text = (el.textContent || "").trim().toLowerCase().replace(/\s+/g, "-").slice(0, 32);
  return sectionId + ":" + text;
}

function isIntakeLink(href) {
  if (!href) return false;
  return (
    href.includes("issues/new") ||
    href.startsWith("mailto:") ||
    href.includes("task-request") ||
    href.includes("/intake")
  );
}

function bindFunnel() {
  const candidates = document.querySelectorAll("a, button[data-copy-wallet]");
  candidates.forEach((el) => {
    if (el.dataset.funnelBound === "1") return;
    el.dataset.funnelBound = "1";

    if (el.tagName === "A") {
      const href = el.getAttribute("href") || "";
      if (isIntakeLink(href)) {
        const step = inferStep(el);
        el.setAttribute("href", annotateOutbound(href, step));
      }
    }

    el.addEventListener("click", () => {
      const step = inferStep(el);
      const href = el.tagName === "A" ? el.getAttribute("href") : null;
      const event = {
        ts: new Date().toISOString(),
        step,
        href,
        kind: el.tagName === "A" ? (isIntakeLink(href || "") ? "intake" : "link") : "wallet-copy",
        ref: document.referrer || null,
      };
      recordFunnelEvent(event);
      try {
        // Visible to anyone who opens devtools — agents can read this on
        // their own visits to debug the funnel.
        console.info("[funnel]", event);
      } catch {
        // ignore
      }
    });
  });
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", bindFunnel);
} else {
  bindFunnel();
}

// Expose a small read-only helper so we can pull recent events from the
// browser console for manual inspection.
window.AIDuoFunnel = {
  events: getFunnelEvents,
  clear: () => localStorage.removeItem(FUNNEL_KEY),
};
