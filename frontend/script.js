const API_BASE = (window.API_BASE || "http://localhost:8000");

const chat = document.getElementById("chat");
const form = document.getElementById("composer");
const text = document.getElementById("text");
const file = document.getElementById("image");

function addMsg(role, content) {
  const el = document.createElement("div");
  el.className = `msg ${role}`;
  const roleEl = document.createElement("div");
  roleEl.className = "role";
  roleEl.textContent = role === "user" ? "你" : "Agent";
  el.appendChild(roleEl);

  const body = document.createElement("div");
  body.textContent = content;
  el.appendChild(body);
  chat.appendChild(el);
  chat.scrollTop = chat.scrollHeight;
}

function addImagePreview(fileObj) {
  const url = URL.createObjectURL(fileObj);
  const el = document.createElement("div");
  el.className = "msg user";
  const roleEl = document.createElement("div");
  roleEl.className = "role";
  roleEl.textContent = "你";
  el.appendChild(roleEl);
  const img = document.createElement("img");
  img.className = "preview";
  img.src = url;
  el.appendChild(img);
  chat.appendChild(el);
  chat.scrollTop = chat.scrollHeight;
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const q = text.value.trim();
  const f = file.files[0];

  if (!q && !f) return;

  if (q) addMsg("user", q);
  if (f) addImagePreview(f);

  const fd = new FormData();
  if (q) fd.append("query", q);
  if (f) fd.append("image", f);
  fd.append("user_id", "web_user");

  addMsg("bot", "思考中…");

  try {
    const res = await fetch(`${API_BASE}/api/chat`, {
      method: "POST",
      body: fd,
    });
    if (!res.ok) {
      throw new Error(`请求失败: ${res.status}`);
    }
    const data = await res.json();
    const last = chat.lastElementChild;
    if (last && last.classList.contains("bot")) {
      last.querySelector("div:nth-child(2)").textContent = data.output || "(无输出)";
    } else {
      addMsg("bot", data.output || "(无输出)");
    }
  } catch (err) {
    const last = chat.lastElementChild;
    const msg = `出错了: ${err.message}`;
    if (last && last.classList.contains("bot")) {
      last.querySelector("div:nth-child(2)").textContent = msg;
    } else {
      addMsg("bot", msg);
    }
  } finally {
    text.value = "";
    file.value = "";
  }
});

