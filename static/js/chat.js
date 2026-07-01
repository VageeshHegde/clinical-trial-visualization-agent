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

document.addEventListener("DOMContentLoaded", () => {
  const chatForm = document.getElementById("chat-form");
  const chatInput = document.getElementById("chat-input");
  const chatMessages = document.getElementById("chat-messages");
  const submitBtn = document.getElementById("chat-submit");
  const submitIcon = document.getElementById("chat-submit-icon");

  if (!chatForm || !chatInput || !chatMessages) return;

  document.querySelectorAll(".welcome-example").forEach((button) => {
    button.addEventListener("click", () => {
      chatInput.value = button.textContent.trim();
      chatInput.focus();
    });
  });

  function setLoading(isLoading) {
    submitBtn.disabled = isLoading;
    chatInput.disabled = isLoading;
    if (submitIcon) {
      submitIcon.className = isLoading
        ? "fa-solid fa-spinner fa-spin"
        : "fa-solid fa-paper-plane";
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
      chip.addEventListener("click", () => {
        chatInput.value = question;
        chatInput.focus();
      });
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
    setLoading(true);

    const thinking = appendMessage("assistant", "Searching ClinicalTrials.gov…", "message-loading");

    try {
      const response = await fetch("/api/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question }),
      });

      const payload = await response.json();
      thinking.remove();

      if (!response.ok) {
        const detail = payload?.detail || "Request failed.";
        appendMessage("assistant", detail, "message-error");
        return;
      }

      appendMessage("assistant", payload.visualization?.summary || "Here are the results.");
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

  chatInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      chatForm.requestSubmit();
    }
  });
});
