const messagesEl = document.getElementById("messages");
const formEl = document.getElementById("chat-form");
const inputEl = document.getElementById("chat-input");
const sendBtn = document.getElementById("send-btn");
const resetBtn = document.getElementById("reset-btn");
const providerSelect = document.getElementById("provider-select");
const apiKeyInput = document.getElementById("api-key-input");

let sessionId = localStorage.getItem("compare_triage_session_id") || null;
const welcomeHtml = messagesEl.innerHTML; // single source of truth for the greeting shown on load and on reset

// Bring-your-own-token: provider choice + one API key per provider, kept only
// in this browser's localStorage - never written anywhere server-side unless
// the user sends a chat message, and even then only used for that request.
const apiKeyStorageKey = (provider) => `compare_triage_api_key_${provider}`;

function loadSettings() {
  const savedProvider = localStorage.getItem("compare_triage_provider");
  if (savedProvider) providerSelect.value = savedProvider;
  apiKeyInput.value = localStorage.getItem(apiKeyStorageKey(providerSelect.value)) || "";
}

providerSelect.addEventListener("change", () => {
  localStorage.setItem("compare_triage_provider", providerSelect.value);
  apiKeyInput.value = localStorage.getItem(apiKeyStorageKey(providerSelect.value)) || "";
});

apiKeyInput.addEventListener("input", () => {
  const key = apiKeyStorageKey(providerSelect.value);
  if (apiKeyInput.value) {
    localStorage.setItem(key, apiKeyInput.value);
  } else {
    localStorage.removeItem(key);
  }
});

loadSettings();

function escapeHtml(text) {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

// Small, dependency-free renderer for the subset of markdown the agent
// actually produces: headers, bold, bullet/numbered lists (with real
// indentation-based nesting - the agent's replies routinely nest a "Dependent
// Failures" bullet -> a numbered sub-list -> bulleted detail lines three
// levels deep), hr, inline code.
function renderMarkdown(raw) {
  const lines = escapeHtml(raw).split("\n");
  let html = "";
  let paragraph = [];
  // Stack of open <ul>/<ol> frames, outermost first. Each frame's <li> is
  // left unclosed (no "</li>" written yet) so a deeper-indented line can
  // nest a new list inside it before that <li> finally closes.
  const listStack = []; // { indent, type: "ul" | "ol" }

  const inline = (text) =>
    text
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/`(.+?)`/g, "<code>$1</code>");

  const flushParagraph = () => {
    if (paragraph.length) {
      html += `<p>${paragraph.join(" ")}</p>`;
      paragraph = [];
    }
  };
  // Closes list frames from the innermost out, down to (but not including)
  // one with indent <= minIndent.
  const closeListsDeeperThan = (minIndent) => {
    while (listStack.length && listStack[listStack.length - 1].indent > minIndent) {
      html += `</li></${listStack.pop().type}>`;
    }
  };
  const closeAllLists = () => closeListsDeeperThan(-1);

  for (const rawLine of lines) {
    const stripped = rawLine.replace(/\s+$/, "");
    const indentMatch = stripped.match(/^(\s*)(.*)$/s);
    const indent = indentMatch[1].length;
    const line = indentMatch[2];

    if (line === "") {
      flushParagraph();
      closeAllLists();
      continue;
    }
    if (/^-{3,}$/.test(line)) {
      flushParagraph();
      closeAllLists();
      html += "<hr>";
      continue;
    }
    const headerMatch = line.match(/^(#{1,4})\s+(.*)$/);
    if (headerMatch) {
      flushParagraph();
      closeAllLists();
      const level = Math.min(headerMatch[1].length + 2, 4); // ### -> h4 (bubble-scale)
      html += `<h${level}>${inline(headerMatch[2])}</h${level}>`;
      continue;
    }

    const bulletMatch = line.match(/^[*-]\s+(.*)$/);
    const numberedMatch = !bulletMatch && line.match(/^\d+\.\s+(.*)$/);
    if (bulletMatch || numberedMatch) {
      flushParagraph();
      const type = bulletMatch ? "ul" : "ol";
      const content = (bulletMatch || numberedMatch)[1];

      closeListsDeeperThan(indent);
      const top = listStack[listStack.length - 1];
      if (!top || top.indent < indent) {
        html += `<${type}>`;
        listStack.push({ indent, type });
      } else if (top.type !== type) {
        // same indent, different marker style - treat as a new list at this level
        html += `</li></${top.type}><${type}>`;
        listStack[listStack.length - 1] = { indent, type };
      } else {
        html += "</li>";
      }
      html += `<li>${inline(content)}`; // left open - may get a nested list appended
      continue;
    }

    closeAllLists();
    paragraph.push(inline(line));
  }
  flushParagraph();
  closeAllLists();
  return html;
}

// Compact interactive checklist for one account's classified dependent failures -
// checkboxes pre-checked exactly where the model said canBeReprocessed:true. The
// "Generate Reprocess Script" button doesn't call any dedicated endpoint - it just
// composes a plain chat message naming the checked correlationIds and sends it
// through the normal pipeline, so the model calls generate_reprocess_script itself
// and the whole thing stays one conversation, not a separate flow.
function renderReprocessPicker(account) {
  const picker = document.createElement("div");
  picker.className = "reprocess-picker";
  if (account.primaryCorrelationId) {
    picker.dataset.primaryCorrelationId = account.primaryCorrelationId;
  }

  const heading = document.createElement("div");
  heading.className = "picker-heading";
  heading.textContent = `Account ${account.accountNumber}`;
  picker.appendChild(heading);

  if (!account.diagnostics || account.diagnostics.length === 0) {
    const note = document.createElement("p");
    note.className = "picker-note";
    note.textContent = "No dependent failures to select.";
    picker.appendChild(note);
    return picker;
  }

  for (const d of account.diagnostics) {
    const row = document.createElement("label");
    row.className = "check-row";
    row.innerHTML = `
      <input type="checkbox" class="reprocess-checkbox" data-correlation-id="${escapeHtml(d.correlationId)}" ${
        d.canBeReprocessed ? "checked" : ""
      } />
      <span>
        <code>${escapeHtml(d.correlationId)}</code>
        <span class="reprocess-verdict ${d.canBeReprocessed ? "verdict-true" : "verdict-false"}">${
          d.canBeReprocessed ? "reprocessable" : "not reprocessable"
        }</span>
        - ${escapeHtml(d.failureReason)}
      </span>`;
    picker.appendChild(row);
  }

  const actions = document.createElement("div");
  actions.className = "picker-actions";
  const generateBtn = document.createElement("button");
  generateBtn.className = "ghost-btn generate-script-btn";
  generateBtn.type = "button";
  generateBtn.textContent = "Generate Reprocess Script";
  actions.appendChild(generateBtn);
  picker.appendChild(actions);

  return picker;
}

function renderScriptOutput(script) {
  const wrapper = document.createElement("div");
  wrapper.className = "script-output";

  const pre = document.createElement("pre");
  pre.className = "script-block";
  pre.textContent = script;
  wrapper.appendChild(pre);

  const actions = document.createElement("div");
  actions.className = "script-actions";
  actions.innerHTML = `
    <button class="ghost-btn copy-script-btn" type="button">Copy</button>
    <button class="ghost-btn download-script-btn" type="button">Download</button>`;
  wrapper.appendChild(actions);

  return wrapper;
}

function addMessage(
  role,
  content,
  { markdown = true, model = null, tier = null, classification = null, mongoScript = null } = {}
) {
  const wrapper = document.createElement("div");
  wrapper.className = `message ${role}`;
  const bubble = document.createElement("div");
  bubble.className = "bubble";
  if (model) {
    const tag = document.createElement("div");
    tag.className = "model-tag";
    tag.textContent = tier ? `${model} · ${tier}` : model;
    bubble.appendChild(tag);
  }
  const body = document.createElement("div");
  if (markdown) {
    body.innerHTML = renderMarkdown(content);
  } else {
    body.textContent = content;
  }
  bubble.appendChild(body);

  if (classification) {
    for (const account of classification) {
      bubble.appendChild(renderReprocessPicker(account));
    }
  }
  if (mongoScript) {
    bubble.appendChild(renderScriptOutput(mongoScript));
  }

  wrapper.appendChild(bubble);
  messagesEl.appendChild(wrapper);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return wrapper;
}

function addTypingIndicator() {
  const wrapper = document.createElement("div");
  wrapper.className = "message assistant";
  wrapper.id = "typing-indicator";
  wrapper.innerHTML = `<div class="bubble"><span class="typing"><span></span><span></span><span></span></span></div>`;
  messagesEl.appendChild(wrapper);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return wrapper;
}

async function sendMessage(text) {
  addMessage("user", text, { markdown: false });
  inputEl.value = "";
  inputEl.style.height = "auto";
  sendBtn.disabled = true;
  const typingEl = addTypingIndicator();

  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: sessionId,
        message: text,
        provider: providerSelect.value,
        api_key: apiKeyInput.value || null,
      }),
    });
    if (!response.ok) {
      throw new Error(`Server returned ${response.status}`);
    }
    const data = await response.json();
    sessionId = data.session_id;
    localStorage.setItem("compare_triage_session_id", sessionId);
    typingEl.remove();
    if (data.model) {
      addMessage("assistant", data.reply, {
        model: data.model,
        tier: data.tier,
        classification: data.classification,
        mongoScript: data.mongo_script,
      });
    } else {
      addMessage("error", data.reply, { markdown: false });
    }
  } catch (err) {
    typingEl.remove();
    addMessage("error", `Couldn't reach the assistant: ${err.message}`, { markdown: false });
  } finally {
    sendBtn.disabled = false;
    inputEl.focus();
  }
}

formEl.addEventListener("submit", (event) => {
  event.preventDefault();
  const text = inputEl.value.trim();
  if (!text) return;
  sendMessage(text);
});

inputEl.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    formEl.requestSubmit();
  }
});

inputEl.addEventListener("input", () => {
  inputEl.style.height = "auto";
  inputEl.style.height = `${Math.min(inputEl.scrollHeight, 160)}px`;
});

resetBtn.addEventListener("click", async () => {
  try {
    const response = await fetch("/api/reset", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId }),
    });
    const data = await response.json();
    sessionId = data.session_id;
    localStorage.setItem("compare_triage_session_id", sessionId);
  } catch (err) {
    // best-effort - a stale session on the server is harmless, just start a fresh local one
    sessionId = null;
    localStorage.removeItem("compare_triage_session_id");
  }
  messagesEl.innerHTML = welcomeHtml;
});

// Top-level guided menu: clicking "Feature Management" just renders a second-level
// submenu client-side (no round trip) - only a leaf pick (Reconciliation, or one of
// the three config sections) actually composes and sends a chat message.
const FEATURE_MANAGEMENT_OPTIONS = [
  { action: "feature-loanboarding", label: "Loan Boarding" },
  { action: "feature-customersync", label: "Customer Sync" },
  { action: "feature-accountsync", label: "Account Sync" },
];
const FEATURE_MANAGEMENT_CONFIG_NAMES = {
  "feature-loanboarding": "LoanBoarding",
  "feature-customersync": "CustomerSync",
  "feature-accountsync": "AccountSync",
};

function showFeatureManagementSubmenu() {
  const wrapper = document.createElement("div");
  wrapper.className = "message assistant";
  const optionButtons = FEATURE_MANAGEMENT_OPTIONS.map(
    (o) => `<button class="ghost-btn menu-btn" type="button" data-action="${o.action}">${o.label}</button>`
  ).join("");
  wrapper.innerHTML = `<div class="bubble">
    Which configuration would you like to manage?
    <div class="menu-options">${optionButtons}</div>
  </div>`;
  messagesEl.appendChild(wrapper);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

// Delegated because menu buttons / reprocess pickers / script blocks are all added
// to #messages dynamically, long after these listeners are attached.
messagesEl.addEventListener("click", (event) => {
  const menuBtn = event.target.closest(".menu-btn");
  if (menuBtn) {
    const action = menuBtn.dataset.action;
    if (action === "reconciliation") {
      sendMessage("I'd like to do reconciliation - help me investigate Hogan/Alfa customer-sync issues.");
    } else if (action === "feature-management") {
      showFeatureManagementSubmenu();
    } else if (action in FEATURE_MANAGEMENT_CONFIG_NAMES) {
      const configName = FEATURE_MANAGEMENT_CONFIG_NAMES[action];
      sendMessage(`I'd like to do Feature Management for ${configName}. Show me the current configuration.`);
    }
    return;
  }

  const generateBtn = event.target.closest(".generate-script-btn");
  if (generateBtn) {
    const picker = generateBtn.closest(".reprocess-picker");
    const checked = [...picker.querySelectorAll(".reprocess-checkbox:checked")].map((cb) => cb.dataset.correlationId);
    if (checked.length === 0) {
      sendMessage("Don't reprocess anything for this account - I didn't select any failures.");
      return;
    }
    const primary = picker.dataset.primaryCorrelationId;
    const message = primary
      ? `Reprocess these correlationIds: ${checked.join(", ")} (include the primary boarding correlationId ${primary}).`
      : `Reprocess these correlationIds: ${checked.join(", ")}.`;
    sendMessage(message);
    return;
  }

  const copyBtn = event.target.closest(".copy-script-btn");
  if (copyBtn) {
    const scriptText = copyBtn.closest(".script-output").querySelector(".script-block").textContent;
    navigator.clipboard
      .writeText(scriptText)
      .then(() => {
        const original = copyBtn.textContent;
        copyBtn.textContent = "Copied!";
        setTimeout(() => (copyBtn.textContent = original), 1500);
      })
      .catch(() => {});
    return;
  }

  const downloadBtn = event.target.closest(".download-script-btn");
  if (downloadBtn) {
    const scriptText = downloadBtn.closest(".script-output").querySelector(".script-block").textContent;
    const blob = new Blob([scriptText], { type: "application/javascript" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "mongo-script.js";
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  }
});
