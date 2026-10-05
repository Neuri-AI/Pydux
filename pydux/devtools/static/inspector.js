const state = {
    history: [],
    selectedIndex: -1,
    activeIndex: -1,
    currentState: null,
    tab: "diff",
    stream: null,
    replaying: false,
};

const els = {
    history: document.getElementById("history"),
    summary: document.getElementById("summary"),
    content: document.getElementById("content"),
    empty: document.getElementById("empty"),
    dot: document.getElementById("live-dot"),
    liveText: document.getElementById("live-text"),
    undo: document.getElementById("undo-btn"),
    redo: document.getElementById("redo-btn"),
    replay: document.getElementById("replay-btn"),
    export: document.getElementById("export-btn"),
    tabs: [...document.querySelectorAll(".tab")],
};

function json(value) {
    return JSON.stringify(value, null, 2);
}

function escapeHtml(text) {
    return String(text)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;");
}

// Syntax highlighting for JSON output
const TOKEN = /("(?:\\.|[^"\\])*")(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?|[{}\[\],]/g;

function highlight(text) {
    return escapeHtml(text).replace(TOKEN, (match, str, colon, literal) => {
        if (str) {
            return colon
                ? `<span class="syn-key">${str}</span><span class="syn-punct">${colon}</span>`
                : `<span class="syn-string">${str}</span>`;
        }
        if (literal) return `<span class="syn-literal">${literal}</span>`;
        if (/^[{}\[\],]$/.test(match)) return `<span class="syn-punct">${match}</span>`;
        return `<span class="syn-number">${match}</span>`;
    });
}

function setContent(value) {
    els.content.innerHTML = highlight(json(value));
}

function setLive(connected) {
    els.dot.classList.toggle("live", connected);
    els.liveText.textContent = connected ? "Live" : "Disconnected";
}

function selectedTrace() {
    if (state.selectedIndex < 0 || state.selectedIndex >= state.history.length) {
        return null;
    }
    return state.history[state.selectedIndex];
}

function renderHistory() {
    els.summary.textContent = `${state.history.length} traces, active #${state.activeIndex}`;
    els.history.innerHTML = "";

    if (state.history.length === 0) {
        els.empty.style.display = "block";
        els.content.style.display = "none";
        return;
    }

    els.empty.style.display = "none";
    els.content.style.display = "block";

    for (const trace of state.history) {
        const li = document.createElement("li");
        const classes = ["history-item"];
        if (trace.index === state.selectedIndex) classes.push("selected");
        if (trace.index === state.activeIndex) classes.push("current");
        li.className = classes.join(" ");
        li.tabIndex = 0;
        li.innerHTML = `
            <div class="row">
                <span class="action-type">${escapeHtml(trace.action.type)}</span>
                <span class="badge">${trace.index === state.activeIndex ? "current" : ""}</span>
            </div>
            <div class="action-meta">#${trace.index} &middot; ${trace.duration_ms.toFixed(2)} ms &middot; ${new Date(trace.timestamp * 1000).toLocaleTimeString()}</div>
        `;
        const select = () => {
            state.selectedIndex = trace.index;
            renderHistory();
            renderDetail();
        };
        li.addEventListener("click", select);
        li.addEventListener("keydown", (event) => {
            if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                select();
            }
        });
        els.history.appendChild(li);
    }
}

function renderDetail() {
    const trace = selectedTrace();
    if (!trace) {
        els.content.textContent = "No trace selected.";
        return;
    }

    if (state.tab === "diff") {
        setContent({
            action: trace.action.type,
            changed_paths: trace.changed_paths,
            duration_ms: trace.duration_ms,
            timestamp: trace.timestamp,
        });
        return;
    }

    if (state.tab === "state") {
        setContent(trace.next_state ?? state.currentState);
        return;
    }

    setContent(trace.action.payload);
}

async function post(path, body = {}) {
    await fetch(path, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
    });
}

async function fetchSnapshot() {
    const response = await fetch("/api/traces", { cache: "no-store" });
    const payload = await response.json();
    state.history = payload.history || [];
    state.activeIndex = Number.isInteger(payload.active_index) ? payload.active_index : -1;
    if (state.selectedIndex < 0 && state.history.length > 0) {
        state.selectedIndex = state.activeIndex >= 0 ? state.activeIndex : state.history[state.history.length - 1].index;
    }

    const stateResponse = await fetch("/api/state", { cache: "no-store" });
    const statePayload = await stateResponse.json();
    state.currentState = statePayload.state;

    renderHistory();
    renderDetail();
}

function connectStream() {
    if (state.stream) {
        state.stream.close();
    }

    const stream = new EventSource("/api/events");
    state.stream = stream;

    stream.onopen = () => setLive(true);
    stream.onerror = () => setLive(false);

    stream.addEventListener("snapshot", (event) => {
        const payload = JSON.parse(event.data);
        state.history = payload.history || [];
        state.activeIndex = Number.isInteger(payload.active_index) ? payload.active_index : -1;
        state.currentState = payload.state;
        if (state.history.length > 0 && (state.selectedIndex < 0 || state.selectedIndex >= state.history.length)) {
            state.selectedIndex = state.activeIndex >= 0 ? state.activeIndex : state.history[state.history.length - 1].index;
        }
        renderHistory();
        renderDetail();
    });

    stream.addEventListener("trace", (event) => {
        const payload = JSON.parse(event.data);
        const trace = payload.trace;
        const existing = state.history.findIndex((item) => item.index === trace.index);
        if (existing >= 0) {
            state.history[existing] = trace;
        } else {
            state.history.push(trace);
            state.history.sort((a, b) => a.index - b.index);
        }
        state.activeIndex = payload.active_index;
        state.currentState = payload.state;
        if (state.selectedIndex === -1 || state.selectedIndex === payload.prev_active_index || state.selectedIndex === state.activeIndex - 1) {
            state.selectedIndex = trace.index;
        }
        renderHistory();
        renderDetail();
    });
}

els.undo.addEventListener("click", async () => {
    await post("/api/undo");
    await fetchSnapshot();
});

els.redo.addEventListener("click", async () => {
    await post("/api/redo");
    await fetchSnapshot();
});

els.replay.addEventListener("click", async () => {
    if (state.replaying || state.history.length === 0) {
        return;
    }
    state.replaying = true;
    els.replay.disabled = true;
    try {
        for (const trace of state.history) {
            await post("/api/jump", { index: trace.index });
            await new Promise((resolve) => setTimeout(resolve, 170));
        }
    } finally {
        state.replaying = false;
        els.replay.disabled = false;
        await fetchSnapshot();
    }
});

els.export.addEventListener("click", () => {
    const blob = new Blob([json(state.history)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `pydux-traces-${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
});

for (const tab of els.tabs) {
    tab.addEventListener("click", () => {
        for (const t of els.tabs) {
            t.classList.remove("active");
        }
        tab.classList.add("active");
        state.tab = tab.dataset.tab;
        renderDetail();
    });
}

(async () => {
    await fetchSnapshot();
    connectStream();
})();