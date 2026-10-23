const statusNode = document.getElementById("codexSessionsStatus");
const listNode = document.getElementById("codexSessionsList");

function addCell(parent, tag, className, value) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  node.textContent = value;
  parent.append(node);
  return node;
}

async function refreshCodexSessions() {
  try {
    const response = await fetch("http://127.0.0.1:8000/api/codex-sessions", {
      headers: { "X-Operator-Id": localStorage.getItem("slimeops-operator") || "super-admin" },
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    listNode.replaceChildren();
    statusNode.textContent = data.available
      ? `${data.sessions.length} sesiones recientes · datos locales de Codex`
      : "No se encontraron rollouts locales de Codex.";
    for (const session of data.sessions.slice(0, 8)) {
      const row = document.createElement("div");
      row.className = "CodexSessionRow";
      addCell(row, "b", "", session.project);
      addCell(row, "small", "", `${session.status} · ${session.usage?.total_tokens?.toLocaleString("es-ES") ?? "—"} tokens`);
      listNode.append(row);
    }
  } catch {
    statusNode.textContent = "API local desconectada; no se pudieron leer las sesiones.";
  }
}

refreshCodexSessions();
setInterval(refreshCodexSessions, 15000);
