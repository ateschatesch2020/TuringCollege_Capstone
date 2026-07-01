class ChatBot {
  constructor() {
    this.API_URL = "http://localhost:8001";
    this.USER_ID = "user123";
    this.currentSessionId = null;
    this.abortController = null;
    this.uploadAbortController = null;
  }

  async init() {
    const newSessionBtn = document.getElementById("newSessionBtn");
    const resetBtn = document.getElementById("resetBtn");
    const sendBtn = document.getElementById("sendBtn");
    const userInput = document.getElementById("userInput");
    const deleteSessionBtn = document.getElementById("deleteSessionBtn");

    if (newSessionBtn) newSessionBtn.addEventListener("click", () => this.openNewChatModal());
    if (resetBtn) resetBtn.addEventListener("click", () => this.resetSession());
    if (deleteSessionBtn) deleteSessionBtn.addEventListener("click", ()=> this.deleteSession())
    if (sendBtn) {
      sendBtn.addEventListener("click", (e) => {
        e.preventDefault();
        this.handleChatAction();
      });
    }
    
    // enter button implementation:
    if (userInput) {
      userInput.addEventListener("keypress", (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
          e.preventDefault();//prevent new line
          this.sendMessage();
        }
      });
      userInput.focus();// userInput
    }

    const userDisplayName = document.getElementById("userDisplayName");
    if (userDisplayName) userDisplayName.textContent = this.USER_ID;

    const userDisplayCharacter = document.getElementById("userDisplayCharacter");
    if (userDisplayCharacter) userDisplayCharacter.textContent = this.USER_ID.slice(0, 2).toUpperCase();
    
    const uploadDocBtn = document.getElementById("uploadDocBtn");
    const docFileInput = document.getElementById("docFileInput");
    const documentList = document.getElementById("documentList");

    const cancelUploadBtn = document.getElementById("cancelUploadBtn");
    if (cancelUploadBtn) cancelUploadBtn.addEventListener("click", () => this.cancelUpload());

    if (uploadDocBtn) uploadDocBtn.addEventListener("click", () => docFileInput.click());
    if (docFileInput) docFileInput.addEventListener("change", () => {
      if (docFileInput.files[0]) {
        this.uploadDocument(docFileInput.files[0]);
        docFileInput.value = "";
      }
    });
    if (documentList) documentList.addEventListener("click", (e) => {
      const delBtn = e.target.closest(".delete-doc-btn");
      if (delBtn) this.deleteDocument(delBtn.dataset.filename);
      const evalBtn = e.target.closest(".eval-doc-btn");
      if (evalBtn) window.open(`evaluation.html?file=${encodeURIComponent(evalBtn.dataset.filename)}`, "_blank");
    });

    // New Chat modal wiring
    const closeNewChatBtn = document.getElementById("closeNewChatBtn");
    const cancelNewChatBtn = document.getElementById("cancelNewChatBtn");
    const startChatBtn = document.getElementById("startChatBtn");
    const fileSearchBtn = document.getElementById("fileSearchBtn");
    const formCancelUploadBtn = document.getElementById("formCancelUploadBtn");
    if (closeNewChatBtn) closeNewChatBtn.addEventListener("click", () => this.closeNewChatModal());
    if (cancelNewChatBtn) cancelNewChatBtn.addEventListener("click", () => this.closeNewChatModal());
    if (startChatBtn) startChatBtn.addEventListener("click", () => this.startNewChat());
    if (fileSearchBtn) fileSearchBtn.addEventListener("click", () => this.searchFilesInModal());
    if (formCancelUploadBtn) formCancelUploadBtn.addEventListener("click", () => this.cancelUpload());
    document.getElementById("fileSearchKeyword")?.addEventListener("keypress", (e) => {
      if (e.key === "Enter") this.searchFilesInModal();
    });
    document.getElementById("newChatModal")?.addEventListener("click", (e) => {
      if (e.target === document.getElementById("newChatModal")) this.closeNewChatModal();
    });

    //load all sessions on the left side of page
    await this.loadSessions();
    await this.loadDocuments();

    //load chats of the active session
    const savedSession = localStorage.getItem("activeSession");
    // activeSession can be found on the browser F12 -> Application tab -> local storage
    if (savedSession) {
      await this.loadChatHistory(savedSession);
    }
  }

  handleChatAction() {
    if (this.abortController) {
      this.abortController.abort();
      this.abortController = null;
      return;
    }
    this.sendMessage();
  }

  resetSession() {
    localStorage.removeItem("activeSession");
    window.location.reload();
  }
  async renameSession(session_id, currentTitle) {
    const newTitle = prompt("New title:", currentTitle);
    if (!newTitle || newTitle.trim() === currentTitle) return;
    try {
      const res = await fetch(`${this.API_URL}/sessions/${session_id}/rename`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: newTitle.trim() })
      });
      if (res.ok) await this.loadSessions();
    } catch (e) {
      console.log(e);
    }
  }

  async deleteSession(session_id) {
    try {
      const res = await fetch(`${this.API_URL}/sessions/${session_id}`, {
        method: "DELETE"
      });
      if (res.ok) {
        if (this.currentSessionId === session_id) {
          this.currentSessionId = null;
          localStorage.removeItem("activeSession");
          document.getElementById("chatContainer").innerHTML = `
            <div id="welcomeScreen" class="flex flex-col items-center justify-center h-full text-center animate-fade-in px-4">
              <div class="w-24 h-24 bg-white rounded-3xl flex items-center justify-center mb-6 shadow-xl shadow-gray-200 border border-gray-100">
                <i class="fa-solid fa-robot text-4xl text-blue-600"></i>
              </div>
              <h2 class="text-2xl font-bold text-gray-800 mb-2">Hello!</h2>
              <p class="text-gray-500 max-w-md">How can I help you?</p>
            </div>`;
        }
        await this.loadSessions();
      }
    } catch (e) {
      console.log(e);
    }
  }
  async sendMessage() {
    const input = document.getElementById("userInput");
    const sendBtn = document.getElementById("sendBtn");
    const text = input.value.trim();

    if (!text) return;

    if (!this.currentSessionId) {
      alert("Please start a new chat first.");
      return;
    }

    this.abortController = new AbortController();
    const signal = this.abortController.signal;

    input.value = "";
    sendBtn.innerHTML = "<i class='fa-solid fa-stop'></i>";
    sendBtn.classList.remove("bg-blue-600", "hover:bg-blue-700");
    sendBtn.classList.add("bg-red-600", "hover:bg-red-700");

    const chatContainer = document.getElementById("chatContainer");
    if (chatContainer.innerHTML.includes("Empty Chat")) chatContainer.innerHTML = "";

    // add user message
    this.appendMessage("user", text);
    this.scrollToBottom();

    // assistant is thinking
    const botBubble = this.appendMessage("assistant", "...");
    const contentDiv = botBubble.querySelector(".message-content");//get the element with .(class) message-content
    contentDiv.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> Thinking...';

    try {
      const res = await fetch(`${this.API_URL}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: this.currentSessionId, query: text }),
        signal: signal
      });

      //getting the response of llm as stream
      const reader = res.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let isFirstChunk = true;
      let fullText = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        if (signal.aborted) break;

        if (isFirstChunk) {
          contentDiv.innerHTML = "";
          isFirstChunk = false;
        }

        const chunk = decoder.decode(value, { stream: true });
        fullText += chunk;
        contentDiv.innerHTML = this.renderContent(fullText);
        this.scrollToBottom();
      }
      contentDiv.innerHTML = this.renderContent(fullText);
      this.initFileSelectWidgets(contentDiv);
      await this.updateTokenUsage();
    } catch (err) {
      if (err.name === "AbortError") {
        contentDiv.innerHTML = "<span class='text-xs text-red-500 italic'>Interrupted.</span>";
      } else {
        contentDiv.innerHTML = "<span class='text-red-500'>⚠️An error occurred.</span>";
        console.log(err);
      }
    } finally {
      this.abortController = null;
      sendBtn.innerHTML = "<i class='fa-solid fa-paper-plane'></i>";
      sendBtn.classList.remove("bg-red-600", "hover:bg-red-700");
      sendBtn.classList.add("bg-blue-600", "hover:bg-blue-700");
      this.scrollToBottom();
      input.focus();
    }
  }

  async loadSessions() {
    try {
      const res = await fetch(`${this.API_URL}/sessions/${this.USER_ID}`);
      const { sessions } = await res.json();
      const listContainer = document.getElementById("sessionList");

      if (sessions.length === 0) {
        listContainer.innerHTML = '<div class="text-center text-gray-400 text-xs mt-4">No sessions created yet.</div>';
        return;
      }

      listContainer.innerHTML = "";

      sessions.forEach(session => {
        const btn = document.createElement("button");
        const isActive = session.session_id === this.currentSessionId;

        btn.className = `
          w-full text-left p-3 rounded-xl text-sm mb-1 transition-all flex items-center gap-3 border group ${isActive ?
          "bg-blue-50 text-blue-700 border-blue-200 font-medium" :
          "text-gray-600 hover:bg-gray-50 hover:text-gray-900 border-transparent"
        }`;

        btn.innerHTML = `
          <i class="fa-regular fa-message flex-shrink-0 ${isActive ? "text-blue-600" : "text-gray-400"}"></i>
          <span class="truncate flex-1">${session.title}</span>
          <span class="rename-btn flex-shrink-0 w-6 h-6 rounded-md flex items-center justify-center text-gray-400 hover:text-blue-500 hover:bg-blue-50 transition-all opacity-0 group-hover:opacity-100">
            <i class="fa-solid fa-pen text-xs"></i>
          </span>
          <span class="delete-btn flex-shrink-0 w-6 h-6 rounded-md flex items-center justify-center text-gray-400 hover:text-red-500 hover:bg-red-50 transition-all opacity-0 group-hover:opacity-100">
            <i class="fa-solid fa-trash text-xs"></i>
          </span>
        `;

        btn.addEventListener("click", () => this.loadChatHistory(session.session_id));

        const renameBtn = btn.querySelector(".rename-btn");
        renameBtn.addEventListener("click", (e) => {
          e.stopPropagation();
          this.renameSession(session.session_id, session.title);
        });

        const deleteBtn = btn.querySelector(".delete-btn");
        deleteBtn.addEventListener("click", (e) => {
          e.stopPropagation();
          this.deleteSession(session.session_id);
        });

        listContainer.appendChild(btn);
      });
    } catch (e) {
      console.log(e);
    }
  }

  async loadChatHistory(sessionId) {
    this.currentSessionId = sessionId;//assign the clicked session to currentsession
    localStorage.setItem("activeSession", sessionId);
    this.loadSessions();

    try {
      const res = await fetch(`${this.API_URL}/history/${sessionId}`);
      const { messages } = await res.json();
      const chatContainer = document.getElementById("chatContainer");

      chatContainer.innerHTML = "";

      if (messages.length === 0) {
        chatContainer.innerHTML = `<div class="flex flex-col items-center justify-center h-full animate-fade-in p-4">
          <div class="bg-amber-50 border border-amber-200 rounded-xl p-4 max-w-md w-full shadow-sm flex items-start gap-3">
            <div class="bg-amber-100 p-2 rounded-lg text-amber-600"><i class="fa-solid fa-triangle-exclamation"></i></div>
            <div><h3 class="font-bold text-amber-800 text-sm">Empty Chat</h3>
            <p class="text-amber-700 text-xs mt-1">Lets write first message!</p></div></div></div>`;
        return;
      }

      messages.forEach((msg) => this.appendMessage(msg.role, msg.content));
      this.scrollToBottom();
      await this.updateTokenUsage();
    } catch (e) {
      console.error(e);
    }
  }

  async updateTokenUsage() {
    if (!this.currentSessionId) return;
    try {
      const res = await fetch(`${this.API_URL}/sessions/${this.currentSessionId}/token-usage`);
      if (!res.ok) return;
      const { percent } = await res.json();
      if (percent == null) return;
      const el = document.getElementById("contextUsage");
      if (!el) return;
      const bar = el.querySelector(".ctx-bar");
      const label = el.querySelector(".ctx-label");
      const color = percent < 50 ? "bg-green-400" : percent < 80 ? "bg-yellow-400" : "bg-red-400";
      bar.className = `ctx-bar h-1 rounded-full transition-all duration-500 ${color}`;
      bar.style.width = percent + "%";
      label.textContent = `${percent}% context`;
    } catch {}
  }

  openNewChatModal() {
    document.getElementById("newChatTitle").value = "";
    document.getElementById("fileSearchKeyword").value = "";
    document.getElementById("formSearchResults").classList.add("hidden");
    document.getElementById("formSearchResults").innerHTML = "";
    document.getElementById("formUploadProgress").classList.add("hidden");
    document.getElementById("formUploadBar").style.width = "0%";
    const modal = document.getElementById("newChatModal");
    modal.classList.remove("hidden");
    modal.classList.add("flex");
    document.getElementById("newChatTitle").focus();
  }

  closeNewChatModal() {
    const modal = document.getElementById("newChatModal");
    modal.classList.add("hidden");
    modal.classList.remove("flex");
  }

  async searchFilesInModal() {
    const keyword = document.getElementById("fileSearchKeyword").value.trim();
    if (!keyword) return;
    const exact = document.getElementById("exactMatchCheck").checked;
    const contains = document.getElementById("containsNameCheck").checked;
    if (!exact && !contains) {
      alert("Please select at least one search mode (Exact match or Contains in name).");
      return;
    }

    const btn = document.getElementById("fileSearchBtn");
    const loading = document.getElementById("formSearchLoading");
    const resultsEl = document.getElementById("formSearchResults");

    btn.disabled = true;
    loading.classList.remove("hidden");
    resultsEl.classList.add("hidden");

    try {
      const res = await fetch(`${this.API_URL}/form/search`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ keyword, exact_match: exact, contains_name: contains }),
      });
      const data = await res.json();
      resultsEl.innerHTML = this.renderContent(data.result);
      resultsEl.classList.remove("hidden");
      this.initFileSelectWidgets(resultsEl, {
        container: "formUploadProgress",
        stage: "formUploadStage",
        bar: "formUploadBar",
        cancel: "formCancelUploadBtn",
      });
    } catch (e) {
      resultsEl.innerHTML = '<p class="text-xs text-red-400">Search failed. Is the backend running?</p>';
      resultsEl.classList.remove("hidden");
      console.error(e);
    } finally {
      btn.disabled = false;
      loading.classList.add("hidden");
    }
  }

  async startNewChat() {
    const title = document.getElementById("newChatTitle").value.trim() || "New Chat";
    this.closeNewChatModal();
    try {
      const res = await fetch(`${this.API_URL}/sessions/create`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: this.USER_ID, title }),
      });
      const data = await res.json();
      await this.loadChatHistory(data.session_id);
    } catch (error) {
      console.error(error);
    }
  }

  async createNewSession() {
    this.openNewChatModal();
  }

  appendMessage(role, text) {
    const container = document.getElementById("chatContainer");
    const isUser = role === "user";
    const div = document.createElement("div");
    div.className = `flex gap-4 ${isUser ? "flex-row-reverse" : "flex-row"} animate-fade-in group w-full`;

    const avatar = isUser
      ? `<div class="w-9 h-9 rounded-full bg-blue-600 flex-shrink-0 flex items-center justify-center text-xs font-bold text-white shadow-sm ring-2 ring-white">U</div>`
      : `<div class="w-9 h-9 rounded-full bg-white flex-shrink-0 flex items-center justify-center text-xs text-blue-600 shadow-sm border border-gray-200"><i class="fa-solid fa-robot text-lg"></i></div>`;

    const bubbleStyle = isUser
      ? "bg-blue-600 text-white rounded-2xl rounded-tr-none shadow-md shadow-blue-100"
      : "bg-white text-gray-800 border border-gray-200 rounded-2xl rounded-tl-none shadow-sm";

    div.innerHTML =
      avatar +
      `<div class="max-w-[85%] md:max-w-[75%] min-w-0"><div class="message-content text-[15px] leading-relaxed py-3.5 px-5 break-text ${bubbleStyle}">${isUser ? this.escapeHtml(text) : this.renderContent(text)}</div></div>`;

    container.appendChild(div);
    if (!isUser) {
      const msgContent = div.querySelector(".message-content");
      if (msgContent) this.initFileSelectWidgets(msgContent);
    }
    return div;
  }

  renderContent(text) {
    return marked.parse(text, { breaks: true });
  }

  initFileSelectWidgets(container, progressIds = {}) {
    container.querySelectorAll("code.language-file-select").forEach(codeEl => {
      const pre = codeEl.parentElement;
      if (!pre || pre.tagName !== "PRE") return;

      let files;
      try { files = JSON.parse(codeEl.textContent); } catch { return; }
      if (!Array.isArray(files) || files.length === 0) return;

      const widget = document.createElement("div");
      widget.className = "border border-blue-200 rounded-xl p-3 mt-2 mb-1 bg-blue-50 text-sm";

      const itemsHtml = files.map(f => {
        const sizeStr = this.formatFileSize(f.size_bytes);
        const estSec = Math.max(15, Math.round((f.size_bytes || 0) / 20000));
        const estStr = estSec < 60 ? `~${estSec}s` : `~${Math.round(estSec / 60)}m`;
        const isPdf = f.name.toLowerCase().endsWith(".pdf");
        const disabledAttr = isPdf ? "" : 'disabled title="Only PDF files can be uploaded"';
        const dimClass = isPdf ? "" : "opacity-40";
        return `<label class="flex items-center gap-2 py-1 px-1 rounded hover:bg-blue-100 cursor-pointer ${dimClass}">
          <input type="checkbox" class="file-select-cb" data-path="${this.escapeAttr(f.path)}" ${disabledAttr} />
          <i class="fa-solid fa-file-pdf text-red-400 text-xs flex-shrink-0"></i>
          <span class="text-xs text-gray-700 truncate flex-1">${this.escapeHtml(f.name)}</span>
          <span class="text-xs text-gray-400 flex-shrink-0 ml-2">${sizeStr} · ${estStr}</span>
        </label>`;
      }).join("");

      widget.innerHTML = `
        <div class="text-xs font-semibold text-blue-700 mb-2 flex items-center gap-1">
          <i class="fa-solid fa-file-arrow-up"></i> Select files to add to knowledge base
        </div>
        <div class="space-y-0.5">${itemsHtml}</div>
        <div class="mt-2 flex items-center gap-2">
          <button class="file-select-upload-btn bg-blue-600 text-white text-xs px-3 py-1.5 rounded-lg hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors" disabled>
            <i class="fa-solid fa-upload mr-1"></i> Upload Selected
          </button>
          <span class="file-select-status text-xs text-gray-400"></span>
        </div>`;

      pre.replaceWith(widget);

      const uploadBtn = widget.querySelector(".file-select-upload-btn");
      widget.querySelectorAll(".file-select-cb").forEach(cb => {
        cb.addEventListener("change", () => {
          uploadBtn.disabled = widget.querySelectorAll(".file-select-cb:checked").length === 0;
        });
      });

      uploadBtn.addEventListener("click", () => {
        const paths = [...widget.querySelectorAll(".file-select-cb:checked")].map(cb => cb.dataset.path);
        this.ingestPaths(paths, widget, progressIds);
      });
    });
  }

  async ingestPaths(paths, widgetEl, progressIds = {}) {
    const uploadBtn = widgetEl?.querySelector(".file-select-upload-btn");
    const statusEl = widgetEl?.querySelector(".file-select-status");
    const progressContainer = document.getElementById(progressIds.container || "uploadProgress");
    const stageLabel = document.getElementById(progressIds.stage || "uploadStageName");
    const progressBar = document.getElementById(progressIds.bar || "uploadProgressBar");
    const cancelBtn = document.getElementById(progressIds.cancel || "cancelUploadBtn");
    const sidebarBtn = document.getElementById("uploadDocBtn");

    this.uploadAbortController = new AbortController();
    const { signal } = this.uploadAbortController;

    if (uploadBtn) uploadBtn.disabled = true;
    if (sidebarBtn) sidebarBtn.disabled = true;
    if (cancelBtn) cancelBtn.classList.remove("hidden");
    if (progressContainer) progressContainer.classList.remove("hidden");

    const setStage = (stage, pct) => {
      if (stageLabel) stageLabel.textContent = stage;
      if (progressBar) progressBar.style.width = pct + "%";
      if (statusEl) statusEl.textContent = stage;
    };

    try {
      const res = await fetch(`${this.API_URL}/documents/ingest-paths`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ paths }),
        signal,
      });
      if (!res.ok) {
        const err = await res.json();
        if (statusEl) statusEl.textContent = `Error: ${err.detail}`;
        return;
      }
      const reader = res.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split("\n\n");
        buffer = parts.pop();
        for (const part of parts) {
          const line = part.trim();
          if (!line.startsWith("data:")) continue;
          let evt;
          try { evt = JSON.parse(line.slice(5).trim()); } catch { continue; }
          if (evt.error) { setStage(`Error: ${evt.error}`, 0); return; }
          const label = evt.total_files > 1
            ? `[${evt.file_index + 1}/${evt.total_files}] ${evt.stage}`
            : evt.stage;
          setStage(label, evt.progress ?? 0);
          if (evt.stage === "Complete") await this.loadDocuments();
        }
      }
    } catch (e) {
      if (e.name === "AbortError") {
        setStage("Cancelled", 0);
      } else {
        if (statusEl) statusEl.textContent = "Upload failed.";
        console.error(e);
      }
    } finally {
      this.uploadAbortController = null;
      if (sidebarBtn) sidebarBtn.disabled = false;
      if (uploadBtn) uploadBtn.disabled = false;
      if (cancelBtn) cancelBtn.classList.add("hidden");
      setTimeout(() => {
        if (progressContainer) progressContainer.classList.add("hidden");
        if (progressBar) progressBar.style.width = "0%";
      }, 1500);
    }
  }

  formatFileSize(bytes) {
    if (!bytes) return "?";
    if (bytes < 1_048_576) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / 1_048_576).toFixed(1)} MB`;
  }

  escapeAttr(str) {
    return String(str).replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  escapeHtml(text) {
    if (!text) return text;
    return text
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  scrollToBottom() {
    const container = document.getElementById("chatContainer");
    if (container) {
      setTimeout(() => {
        container.scrollTo({
          top: container.scrollHeight,
          behavior: "smooth",
        });
      }, 50);
    }
  }

  async loadDocuments() {
    const list = document.getElementById("documentList");
    if (!list) return;
    try {
      const res = await fetch(`${this.API_URL}/documents`);
      if (!res.ok) {
        list.innerHTML = '<p class="text-xs text-red-400 px-2">Could not load documents.</p>';
        return;
      }
      const { documents } = await res.json();
      if (documents.length === 0) {
        list.innerHTML = '<p class="text-xs text-gray-400 px-2">No documents uploaded.</p>';
        return;
      }
      list.innerHTML = documents.map(name => `
        <div class="flex items-center justify-between text-xs text-gray-600 px-2 py-1 rounded-lg hover:bg-gray-50 group">
          <span class="truncate"><i class="fa-solid fa-file-pdf text-red-400 mr-1.5"></i>${this.escapeHtml(name)}</span>
          <div class="flex items-center gap-1 flex-shrink-0 opacity-0 group-hover:opacity-100 transition-all ml-1">
            <button class="eval-doc-btn text-gray-400 hover:text-indigo-500 transition-colors" data-filename="${this.escapeHtml(name)}" title="Evaluate">
              <i class="fa-solid fa-chart-bar text-xs"></i>
            </button>
            <button class="delete-doc-btn text-gray-400 hover:text-red-500 transition-colors" data-filename="${this.escapeHtml(name)}" title="Delete">
              <i class="fa-solid fa-trash text-xs"></i>
            </button>
          </div>
        </div>`).join("");
    } catch (e) {
      list.innerHTML = '<p class="text-xs text-red-400 px-2">Backend unavailable.</p>';
      console.error(e);
    }
  }

  cancelUpload() {
    if (this.uploadAbortController) {
      this.uploadAbortController.abort();
    }
  }

  async uploadDocument(file) {
    const btn = document.getElementById("uploadDocBtn");
    const progressContainer = document.getElementById("uploadProgress");
    const stageLabel = document.getElementById("uploadStageName");
    const progressBar = document.getElementById("uploadProgressBar");
    const cancelBtn = document.getElementById("cancelUploadBtn");

    this.uploadAbortController = new AbortController();
    const { signal } = this.uploadAbortController;

    if (btn) btn.disabled = true;
    if (cancelBtn) cancelBtn.classList.remove("hidden");
    if (progressContainer) progressContainer.classList.remove("hidden");

    const setStage = (stage, pct) => {
      if (stageLabel) stageLabel.textContent = stage;
      if (progressBar) progressBar.style.width = pct + "%";
    };

    let cancelled = false;
    try {
      const form = new FormData();
      form.append("file", file);
      const res = await fetch(`${this.API_URL}/documents/upload`, { method: "POST", body: form, signal });
      if (!res.ok) {
        const err = await res.json();
        alert(`Upload failed: ${err.detail}`);
        return;
      }
      const reader = res.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split("\n\n");
        buffer = parts.pop();
        for (const part of parts) {
          const line = part.trim();
          if (!line.startsWith("data:")) continue;
          let evt;
          try { evt = JSON.parse(line.slice(5).trim()); } catch { continue; }
          if (evt.error) { alert(`Upload failed: ${evt.error}`); return; }
          setStage(evt.stage, evt.progress ?? 0);
          if (evt.stage === "Complete") await this.loadDocuments();
        }
      }
    } catch (e) {
      if (e.name === "AbortError") {
        cancelled = true;
        setStage("Cancelled", 0);
      } else {
        alert("Upload failed. Is the backend running?");
        console.error(e);
      }
    } finally {
      this.uploadAbortController = null;
      if (btn) btn.disabled = false;
      if (cancelBtn) cancelBtn.classList.add("hidden");
      if (cancelled) {
        setTimeout(() => {
          if (progressContainer) progressContainer.classList.add("hidden");
          if (progressBar) progressBar.style.width = "0%";
        }, 1500);
      } else {
        if (progressContainer) progressContainer.classList.add("hidden");
        if (progressBar) progressBar.style.width = "0%";
      }
    }
  }

  async deleteDocument(filename) {
    if (!confirm(`Remove "${filename}" from the knowledge base?`)) return;
    const list = document.getElementById("documentList");
    const row = list?.querySelector(`[data-filename="${CSS.escape(filename)}"]`)?.closest("div");
    if (row) row.innerHTML = `<span class="text-xs text-gray-400 px-2 italic"><i class="fa-solid fa-circle-notch fa-spin mr-1"></i>Removing from index...</span>`;
    try {
      const res = await fetch(`${this.API_URL}/documents/${encodeURIComponent(filename)}`, { method: "DELETE" });
      if (!res.ok) {
        const err = await res.json();
        alert(`Delete failed: ${err.detail}`);
      }
    } catch (e) {
      alert("Delete failed. Is the backend running?");
      console.error(e);
    } finally {
      await this.loadDocuments();
    }
  }
}
// to ensure that init method will be called after all elements were loaded.
document.addEventListener("DOMContentLoaded", () => {
  const chatbot = new ChatBot();
  chatbot.init();
});
