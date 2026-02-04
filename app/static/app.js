const portsTable = document.getElementById("ports-table");
const tunnelsTable = document.getElementById("tunnels-table");
const refreshPortsButton = document.getElementById("refresh-ports");
const refreshTunnelsButton = document.getElementById("refresh-tunnels");
const debugPanel = document.getElementById("debug-panel");
const debugTitle = document.getElementById("debug-title");
const debugContent = document.getElementById("debug-content");

async function fetchJson(url, options) {
  const response = await fetch(url, options);
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    const detail = payload.detail || "Errore inatteso.";
    throw new Error(detail);
  }
  return response.json();
}

async function loadTunnelLogs(port) {
  try {
    const payload = await fetchJson(`/api/tunnels/${port}/logs`);
    debugTitle.textContent = `Log tunnel ${port}`;
    debugContent.textContent = payload.logs.join("\n") || "Nessun log disponibile.";
    debugPanel.classList.add("visible");
  } catch (error) {
    debugTitle.textContent = `Log tunnel ${port}`;
    debugContent.textContent = `Errore: ${error.message}`;
    debugPanel.classList.add("visible");
  }
}

function hideDebugPanel() {
  debugPanel.classList.remove("visible");
  debugTitle.textContent = "";
  debugContent.textContent = "";
}

function renderPorts(ports) {
  if (!ports.length) {
    portsTable.innerHTML = "<p>Nessuna porta in ascolto trovata.</p>";
    return;
  }

  const rows = ports
    .map(
      (port) => `
      <div class="row">
        <div class="cell">${port.port}</div>
        <div class="cell">${port.service}</div>
        <div class="cell">
          <button data-port="${port.port}" class="start-button">Avvia tunnel</button>
        </div>
      </div>
    `
    )
    .join("");

  portsTable.innerHTML = `
    <div class="row header">
      <div class="cell">Porta</div>
      <div class="cell">Servizio</div>
      <div class="cell">Azioni</div>
    </div>
    ${rows}
  `;

  portsTable.querySelectorAll(".start-button").forEach((button) => {
    button.addEventListener("click", async () => {
      const port = Number(button.dataset.port);
      button.disabled = true;
      try {
        await fetchJson("/api/tunnels", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ port }),
        });
        await loadTunnels();
      } catch (error) {
        alert(error.message);
      } finally {
        button.disabled = false;
      }
    });
  });
}

function renderTunnels(tunnels) {
  if (!tunnels.length) {
    tunnelsTable.innerHTML = "<p>Nessun tunnel attivo.</p>";
    return;
  }

  const rows = tunnels
    .map(
      (tunnel) => `
      <div class="row">
        <div class="cell">${tunnel.port}</div>
        <div class="cell">${tunnel.pid}</div>
        <div class="cell">${tunnel.status || "running"}</div>
        <div class="cell">${tunnel.url ? `<a href="${tunnel.url}" target="_blank">${tunnel.url}</a>` : "In attesa..."}</div>
        <div class="cell">${tunnel.last_output ? tunnel.last_output : "-"}</div>
        <div class="cell">
          <button data-port="${tunnel.port}" class="logs-button">Log</button>
          <button data-port="${tunnel.port}" class="stop-button">Ferma</button>
        </div>
      </div>
    `
    )
    .join("");

  tunnelsTable.innerHTML = `
    <div class="row header">
      <div class="cell">Porta</div>
      <div class="cell">PID</div>
      <div class="cell">Stato</div>
      <div class="cell">URL</div>
      <div class="cell">Ultimo log</div>
      <div class="cell">Azioni</div>
    </div>
    ${rows}
  `;

  tunnelsTable.querySelectorAll(".logs-button").forEach((button) => {
    button.addEventListener("click", async () => {
      const port = Number(button.dataset.port);
      await loadTunnelLogs(port);
    });
  });

  tunnelsTable.querySelectorAll(".stop-button").forEach((button) => {
    button.addEventListener("click", async () => {
      const port = Number(button.dataset.port);
      button.disabled = true;
      try {
        await fetchJson(`/api/tunnels/${port}`, { method: "DELETE" });
        await loadTunnels();
      } catch (error) {
        alert(error.message);
      } finally {
        button.disabled = false;
      }
    });
  });
}

async function loadPorts() {
  try {
    const ports = await fetchJson("/api/ports");
    renderPorts(ports);
  } catch (error) {
    portsTable.innerHTML = `<p>Errore: ${error.message}</p>`;
  }
}

async function loadTunnels() {
  try {
    const tunnels = await fetchJson("/api/tunnels");
    renderTunnels(tunnels);
  } catch (error) {
    tunnelsTable.innerHTML = `<p>Errore: ${error.message}</p>`;
  }
}

refreshPortsButton.addEventListener("click", loadPorts);
refreshTunnelsButton.addEventListener("click", loadTunnels);
document.getElementById("debug-close").addEventListener("click", hideDebugPanel);

loadPorts();
loadTunnels();
setInterval(loadTunnels, 4000);
