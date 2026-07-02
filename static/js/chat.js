function escapeHtml(text) {
  return String(text)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function formatMetaKey(key) {
  return key.replaceAll("_", " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function formatMetaValue(value) {
  if (value === null || value === undefined) return "—";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function formatApiError(payload) {
  const detail = payload?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (typeof item === "string") return item;
        const message = item?.msg || "Invalid request.";
        return message.replace(/^Value error,\s*/i, "");
      })
      .join(" ");
  }
  return "Request failed.";
}

function updateFiltersPanel(result) {
  const badge = document.getElementById("filter-badge");
  const metaList = document.getElementById("filters-meta");
  const viz = result?.visualization;
  if (!metaList) return;

  metaList.innerHTML = "";
  const meta = viz?.meta || {};
  const entries = Object.entries(meta);

  if (badge) {
    badge.textContent = entries.length ? "Applied" : "No filters";
  }

  if (!entries.length) {
    const div = document.createElement("div");
    div.innerHTML = "<dt>Query</dt><dd>No filter metadata returned</dd>";
    metaList.appendChild(div);
    return;
  }

  entries.forEach(([key, value]) => {
    const div = document.createElement("div");
    div.innerHTML = `
      <dt>${escapeHtml(formatMetaKey(key))}</dt>
      <dd>${escapeHtml(formatMetaValue(value))}</dd>
    `;
    metaList.appendChild(div);
  });
}

function updateVisualizationPanel(result) {
  const viz = result?.visualization;
  if (!viz) return;

  const title = document.getElementById("viz-title");
  const subtitle = document.getElementById("viz-subtitle");
  const chartType = document.getElementById("viz-chart-type");
  const trialsCard = document.getElementById("trials-card");

  if (title) title.textContent = viz.title || "Visualization";
  if (subtitle) subtitle.hidden = true;
  if (chartType) {
    chartType.textContent = viz.chart_type || "";
    chartType.hidden = !viz.chart_type;
  }

  window.VisualizationRenderer?.renderVisualization(viz);
  window.VisualizationRenderer?.renderTrials(result.trials || []);

  if (trialsCard) {
    trialsCard.hidden = !(result.trials && result.trials.length > 0);
  }

  updateFiltersPanel(result);
}

window.VisualizationPanel = { updateVisualizationPanel };

const SPINNER_ICON_CLASS = "fa-solid fa-spinner fa-spin";
const SEND_ICON_CLASS = "fa-solid fa-paper-plane";
const CHAT_CONTEXT_MAX_MESSAGES = 10;

document.addEventListener("DOMContentLoaded", () => {
  const chatForm = document.getElementById("chat-form");
  const chatInput = document.getElementById("chat-input");
  const chatMessages = document.getElementById("chat-messages");
  const submitBtn = document.getElementById("chat-submit");
  const submitIcon = document.getElementById("chat-submit-icon");

  if (!chatForm || !chatInput || !chatMessages) return;

  let conversationHistory = [];

  chatMessages.addEventListener("click", (event) => {
    const chip = event.target.closest(".follow-up-chip");
    if (!chip) return;
    chatInput.value = chip.textContent.trim();
    resizeChatInput();
    chatInput.focus();
  });

  function resizeChatInput() {
    chatInput.style.height = "auto";
    const maxHeight = parseFloat(getComputedStyle(chatInput).maxHeight) || Infinity;
    const nextHeight = Math.min(chatInput.scrollHeight, maxHeight);
    chatInput.style.height = `${nextHeight}px`;
    chatInput.style.overflowY = chatInput.scrollHeight > maxHeight ? "auto" : "hidden";
  }

  function setLoading(isLoading) {
    submitBtn.disabled = isLoading;
    chatInput.disabled = isLoading;
    if (submitIcon) {
      submitIcon.className = isLoading ? SPINNER_ICON_CLASS : SEND_ICON_CLASS;
    }
  }

  function appendMessage(role, text, extraClass = "") {
    const wrapper = document.createElement("div");
    wrapper.className = `message message-${role} ${extraClass}`.trim();
    wrapper.innerHTML = `<div class="message-bubble">${escapeHtml(text)}</div>`;
    chatMessages.appendChild(wrapper);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return wrapper;
  }

  function appendLoadingMessage(text = "Searching ClinicalTrials.gov…") {
    const wrapper = document.createElement("div");
    wrapper.className = "message message-assistant message-loading";
    wrapper.innerHTML = `
      <div class="message-bubble">
        <i class="${SPINNER_ICON_CLASS}" aria-hidden="true"></i>
        <span>${escapeHtml(text)}</span>
      </div>
    `;
    chatMessages.appendChild(wrapper);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return wrapper;
  }

  function appendFollowUpQuestions(questions) {
    if (!questions?.length) return;

    const wrapper = document.createElement("div");
    wrapper.className = "message message-assistant follow-ups";
    const list = document.createElement("div");
    list.className = "follow-up-list";

    questions.forEach((question) => {
      const chip = document.createElement("button");
      chip.type = "button";
      chip.className = "follow-up-chip";
      chip.textContent = question;
      list.appendChild(chip);
    });

    wrapper.appendChild(list);
    chatMessages.appendChild(wrapper);
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  chatForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const question = chatInput.value.trim();
    if (!question) return;

    appendMessage("user", question);
    chatInput.value = "";
    resizeChatInput();
    setLoading(true);

    const thinking = appendLoadingMessage();

    try {
      const response = await fetch("/api/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question,
          history: conversationHistory.slice(-CHAT_CONTEXT_MAX_MESSAGES),
        }),
      });

      const payload = await response.json();
      thinking.remove();

      if (!response.ok) {
        appendMessage("assistant", formatApiError(payload), "message-error");
        return;
      }

      const summary = payload.visualization?.summary || "Here are the results.";
      conversationHistory.push({ role: "user", content: question });
      conversationHistory.push({ role: "assistant", content: summary });
      if (conversationHistory.length > CHAT_CONTEXT_MAX_MESSAGES * 2) {
        conversationHistory = conversationHistory.slice(-CHAT_CONTEXT_MAX_MESSAGES * 2);
      }

      appendMessage("assistant", summary);
      appendFollowUpQuestions(payload.follow_questions);
      window.VisualizationPanel?.updateVisualizationPanel(payload);
    } catch (error) {
      thinking.remove();
      appendMessage(
        "assistant",
        error instanceof Error ? error.message : "Network error. Please try again.",
        "message-error"
      );
    } finally {
      setLoading(false);
      chatInput.focus();
    }
  });

  chatInput.addEventListener("input", resizeChatInput);

  chatInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      chatForm.requestSubmit();
    }
  });

  resizeChatInput();
});
