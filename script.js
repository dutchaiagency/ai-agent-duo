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
