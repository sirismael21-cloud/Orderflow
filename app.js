const el = (id) => document.getElementById(id);

function fmt(n, digits = 2) {
  if (n === null || n === undefined) return "–";
  return Number(n).toLocaleString(undefined, { maximumFractionDigits: digits });
}

async function refreshStatus() {
  try {
    const res = await fetch("/api/status");
    const s = await res.json();

    el("badge").textContent = s.testnet ? "TESTNET" : "LIVE";
    el("badge").className = "badge " + (s.testnet ? "testnet" : "live");
    el("symbol").textContent = s.symbol;
    el("price").textContent = s.last_price ? fmt(s.last_price) : "–";

    if (s.risk_halted) {
      el("halt-banner").hidden = false;
      el("halt-reason").textContent = s.halt_reason;
    } else {
      el("halt-banner").hidden = true;
    }

    el("position").textContent = s.open_position
      ? `${s.open_position.side} qty=${fmt(s.open_position.qty, 6)} entry=${fmt(s.open_position.entry)} SL=${fmt(s.open_position.sl)} TP=${fmt(s.open_position.tp)}`
      : "Flat";

    if (s.balances) {
      el("balances").textContent =
        `${s.balances.base}: ${fmt(s.balances.base_free, 6)}   ${s.balances.quote}: ${fmt(s.balances.quote_free)}`;
    }

    el("log").textContent = s.log
      .map((l) => `[${new Date(l.ts * 1000).toLocaleTimeString()}] ${l.msg}`)
      .join("\n");
    el("log").scrollTop = el("log").scrollHeight;
  } catch (e) {
    el("badge").textContent = "offline";
  }
}

function connectWS() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${proto}://${location.host}/ws/orderflow`);
  ws.onmessage = (evt) => {
    const d = JSON.parse(evt.data);
    if (d.last_price) el("price").textContent = fmt(d.last_price);
    if (d.obi !== null && d.obi !== undefined) {
      el("obi").textContent = `${(d.obi * 100).toFixed(1)}% bid-heavy`;
      el("obi-fill").style.width = `${d.obi * 100}%`;
    }
    if (d.cvd !== undefined) {
      el("cvd").textContent = fmt(d.cvd, 4);
      el("cvd").style.color = d.cvd >= 0 ? "var(--green)" : "var(--red)";
    }
  };
  ws.onclose = () => setTimeout(connectWS, 2000);
}

el("startBtn").onclick = () => fetch("/api/start", { method: "POST" }).then(refreshStatus);
el("stopBtn").onclick = () => fetch("/api/stop", { method: "POST" }).then(refreshStatus);
el("closeBtn").onclick = () => {
  if (confirm("Close the open position at market now?")) {
    fetch("/api/close", { method: "POST" }).then(refreshStatus);
  }
};
el("killBtn").onclick = () => {
  if (confirm("KILL SWITCH: stop the bot and halt trading until you manually resume?")) {
    fetch("/api/kill", { method: "POST" }).then(refreshStatus);
  }
};

connectWS();
refreshStatus();
setInterval(refreshStatus, 3000);
