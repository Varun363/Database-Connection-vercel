async function api(url, options = {}) {
  const config = { ...options, headers: { ...(options.headers || {}) } };

  if (config.body && typeof config.body !== "string") {
    config.headers["Content-Type"] = "application/json";
    config.body = JSON.stringify(config.body);
  }

  const response = await fetch(url, config);
  const contentType = response.headers.get("content-type") || "";
  const data = contentType.includes("application/json")
    ? await response.json()
    : await response.text();

  if (!response.ok) {
    throw new Error(data?.detail || data?.message || "Request failed");
  }
  return data;
}

function showError(error) {
  console.error(error);
  if (typeof toast === "function") toast(error.message || String(error));
}

function toast(message) {
  let el = document.getElementById("toast");
  if (!el) {
    el = document.createElement("div");
    el.id = "toast";
    el.style.cssText = "position:fixed;right:24px;bottom:24px;padding:14px 18px;border-radius:12px;background:#111;color:#fff;z-index:9999;box-shadow:0 10px 30px rgba(0,0,0,.2)";
    document.body.appendChild(el);
  }
  el.textContent = message;
  clearTimeout(window.__toastTimer);
  window.__toastTimer = setTimeout(() => el.remove(), 2800);
}

function toggleSidebar() {
  document.getElementById("sidebar")?.classList.toggle("open");
}

function openModal(id) {
  document.getElementById(id)?.classList.add("open");
}

function closeModal(id) {
  document.getElementById(id)?.classList.remove("open");
}

function setupDates() {
  const today = new Date().toISOString().split("T")[0];
  const tomorrow = new Date(Date.now() + 86400000).toISOString().split("T")[0];
  const checkIn = document.getElementById("checkIn");
  const checkOut = document.getElementById("checkOut");
  if (checkIn) checkIn.min = today;
  if (checkOut) checkOut.min = tomorrow;
}

function filterRooms() {
  const query = (document.getElementById("roomSearch")?.value || "").toLowerCase();
  const type = document.getElementById("typeFilter")?.value || "";

  document.querySelectorAll("#roomGrid .room-card").forEach(card => {
    const text = card.dataset.search?.toLowerCase() || card.textContent.toLowerCase();
    const cardType = card.dataset.type || "";
    card.style.display =
      (!query || text.includes(query)) && (!type || cardType === type)
        ? ""
        : "none";
  });
}

function openBooking(id, type, price) {
  document.getElementById("bookingRoomId").value = id;
  document.getElementById("bookingTitle").textContent = `Book ${type}`;
  document.getElementById("bookingPrice").textContent = `₹${Number(price).toLocaleString("en-IN")} / night`;
  openModal("bookingModal");
}

async function submitBooking(event) {
  event.preventDefault();

  try {
    const result = await api("/api/bookings", {
      method: "POST",
      body: {
        room_id: Number(document.getElementById("bookingRoomId").value),
        check_in: document.getElementById("checkIn").value,
        check_out: document.getElementById("checkOut").value,
        guests: Number(document.getElementById("bookingGuests").value),
      }
    });

    closeModal("bookingModal");
    toast(`Booking #${result.booking_id} confirmed`);
    setTimeout(() => location.href = "/bookings", 700);
  } catch (e) {
    showError(e);
  }
}

async function loadIssues() {
  try {
    const issues = await api("/api/issues");
    const body = document.getElementById("issueBody");
    if (!body) return;

    body.innerHTML = issues.map(x => `
      <tr>
        <td><b>${escapeHtml(x.title)}</b><small>${escapeHtml(x.description || "")}</small></td>
        <td>${escapeHtml(x.room || "—")}</td>
        <td>${escapeHtml(x.category)}</td>
        <td>${escapeHtml(x.priority)}</td>
        <td><span class="pill">${escapeHtml(x.status)}</span></td>
        <td>—</td>
      </tr>
    `).join("");
  } catch (e) { showError(e); }
}

async function createIssue(event) {
  event.preventDefault();
  try {
    await api("/api/issues", {
      method: "POST",
      body: {
        title: document.getElementById("issueTitle").value,
        room: document.getElementById("issueRoom").value,
        category: document.getElementById("issueCategory").value,
        priority: document.getElementById("issuePriority").value,
        description: document.getElementById("issueDescription").value,
      }
    });
    closeModal("issueModal");
    toast("Issue created");
    await loadIssues();
  } catch (e) { showError(e); }
}

async function loadTasks() {
  try {
    const tasks = await api("/api/tasks");
    const body = document.getElementById("taskBody");
    if (!body) return;

    body.innerHTML = tasks.map(x => `
      <tr>
        <td><b>${escapeHtml(x.title)}</b></td>
        <td>${escapeHtml(x.room || "—")}</td>
        <td>${escapeHtml(x.assignee || "Unassigned")}</td>
        <td>${escapeHtml(x.priority)}</td>
        <td><span class="pill">${escapeHtml(x.status)}</span></td>
        <td>—</td>
      </tr>
    `).join("");

    const stats = document.getElementById("taskStats");
    if (stats) {
      const pending = tasks.filter(x => x.status === "Pending").length;
      const progress = tasks.filter(x => x.status === "In Progress").length;
      const done = tasks.filter(x => x.status === "Completed").length;
      stats.innerHTML = `
        <div><span>Pending</span><b>${pending}</b></div>
        <div><span>In Progress</span><b>${progress}</b></div>
        <div><span>Completed</span><b>${done}</b></div>`;
    }
  } catch (e) { showError(e); }
}

function openTaskModal() {
  openModal("taskModal");
}

async function createTask(event) {
  event.preventDefault();
  try {
    await api("/api/tasks", {
      method: "POST",
      body: {
        title: document.getElementById("taskTitle").value,
        type: document.getElementById("taskType").value,
        room: document.getElementById("taskRoom").value,
        priority: document.getElementById("taskPriority").value,
        assignee: document.getElementById("taskAssignee").value,
      }
    });
    closeModal("taskModal");
    toast("Task assigned");
    await loadTasks();
  } catch (e) { showError(e); }
}

async function loadStaff() {
  try {
    const staff = await api("/api/staff");
    const body = document.querySelector("#staffTable tbody");
    if (!body) return;

    body.innerHTML = staff.map(x => `
      <tr>
        <td><b>${escapeHtml(x.name)}</b></td>
        <td>${escapeHtml(x.role)}</td>
        <td>${escapeHtml(x.department)}</td>
        <td><span class="pill success">${escapeHtml(x.status)}</span></td>
        <td>${escapeHtml(x.email)}</td>
      </tr>
    `).join("");

    const select = document.getElementById("taskAssignee");
    if (select) {
      select.innerHTML = `<option value="">Unassigned</option>` +
        staff.map(x => `<option value="${escapeAttr(x.name)}">${escapeHtml(x.name)}</option>`).join("");
    }
  } catch (e) { showError(e); }
}

async function loadAllocation() {
  try {
    const bookings = await api("/api/bookings");
    const body = document.getElementById("allocationBody");
    if (!body) return;

    body.innerHTML = bookings.map(x => `
      <tr>
        <td>${escapeHtml(x.room_number || "Guest")}</td>
        <td>${escapeHtml(x.room)}</td>
        <td>${escapeHtml(x.check_in)} → ${escapeHtml(x.check_out)}</td>
        <td>${escapeHtml(x.room_number)}</td>
        <td><button class="btn small">Allocated</button></td>
      </tr>
    `).join("");
  } catch (e) { showError(e); }
}

async function initDashboard() {
  try {
    const data = await api("/api/dashboard");

    const stats = document.getElementById("dashStats");
    if (stats) {
      stats.innerHTML = `
        <div><span>Rooms</span><b>${data.rooms}</b></div>
        <div><span>Bookings</span><b>${data.bookings}</b></div>
        <div><span>Pending Tasks</span><b>${data.pending_tasks}</b></div>
        <div><span>Open Issues</span><b>${data.open_issues}</b></div>`;
    }
  } catch (e) { showError(e); }
}

async function initAIPage() {
  // Safe base implementation. Your existing AI UI can be connected to /ai later.
  console.log("ResortOS AI page initialized");
}

async function loadAIInsight() {
  const el = document.getElementById("aiInsight");
  if (el) el.textContent = "Live operations data is connected.";
}

async function sendAIChat(event) {
  event.preventDefault();
  const input = document.getElementById("aiInput");
  const messages = document.getElementById("aiMessages");
  if (!input || !messages || !input.value.trim()) return;

  const question = input.value.trim();
  messages.insertAdjacentHTML("beforeend",
    `<div class="ai-msg user"><b>You</b><span>${escapeHtml(question)}</span></div>`);
  input.value = "";

  // Keep this as a frontend fallback until the AI endpoint is defined.
  messages.insertAdjacentHTML("beforeend",
    `<div class="ai-msg bot"><b>ResortOS AI</b><span>I received your request. Connect your AI provider endpoint to enable live AI responses.</span></div>`);
}

function aiAsk(text) {
  const input = document.getElementById("aiInput");
  if (input) {
    input.value = text;
    input.focus();
  }
}

async function triageIssue(event) {
  event.preventDefault();
  const result = document.getElementById("triageResult");
  if (!result) return;

  result.textContent = "AI triage endpoint is ready to be connected. For now, the issue can be created from the Issues page.";
}

function showNotifications() {
  toast("No new notifications");
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function escapeAttr(value) {
  return escapeHtml(value);
}

document.addEventListener("DOMContentLoaded", () => {
  setupDates();
});
