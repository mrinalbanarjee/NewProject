const messagesEl = document.getElementById("messages");
const formEl = document.getElementById("chat-form");
const inputEl = document.getElementById("chat-input");
const sendBtn = document.getElementById("send-btn");
const resetBtn = document.getElementById("reset-btn");

let sessionId = localStorage.getItem("compare_triage_session_id") || null;
const welcomeHtml = messagesEl.innerHTML; // single source of truth for the greeting shown on load and on reset

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

function addMessage(role, content, { markdown = true } = {}) {
  const wrapper = document.createElement("div");
  wrapper.className = `message ${role}`;
  const bubble = document.createElement("div");
  bubble.className = "bubble";
  if (markdown) {
    bubble.innerHTML = renderMarkdown(content);
  } else {
    bubble.textContent = content;
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
      body: JSON.stringify({ session_id: sessionId, message: text }),
    });
    if (!response.ok) {
      throw new Error(`Server returned ${response.status}`);
    }
    const data = await response.json();
    sessionId = data.session_id;
    localStorage.setItem("compare_triage_session_id", sessionId);
    typingEl.remove();
    addMessage("assistant", data.reply);
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
