/* TechCorp Storefront — frontend application.
 *
 * Security-relevant note (VULN-005 / stored XSS):
 *   `inject(el, html)` is the OUTPUT SINK for user/admin-controlled strings
 *   (user bios, product descriptions). In vulnerable mode it uses innerHTML;
 *   in secure mode it uses textContent so the content can never execute.
 *   The mode is detected from GET /health at startup.
 */

const state = {
  token: localStorage.getItem("tc_token") || null,
  user: null,
  mode: "secure",
  view: "products",
  products: [],
  selectedProduct: null,
};

const app = document.getElementById("app");
const nav = document.getElementById("nav");
const toastEl = document.getElementById("toast");
let toastTimer = null;

/* ------------------------------------------------------------------ */
/* helpers                                                            */
/* ------------------------------------------------------------------ */

function toast(msg) {
  toastEl.textContent = msg;
  toastEl.classList.remove("hidden");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toastEl.classList.add("hidden"), 3500);
}

function esc(s) {
  return String(s == null ? "" : s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

/* VULN-005 output sink */
function inject(el, html) {
  if (state.mode === "vulnerable") {
    el.innerHTML = html; // intentional lab sink
  } else {
    el.textContent = html; // remediated: content is rendered as text
  }
}

async function api(path, options = {}) {
  const opts = Object.assign({}, options);
  opts.headers = Object.assign({ "Content-Type": "application/json" }, opts.headers || {});
  if (state.token) opts.headers.Authorization = `Bearer ${state.token}`;
  const res = await fetch(path, opts);
  if (res.status === 204) return null;
  let body = null;
  try { body = await res.json(); } catch (e) { /* no body */ }
  if (!res.ok) {
    let detail = "Request failed";
    if (body && body.detail) detail = body.detail;
    throw new Error(detail);
  }
  return body;
}

/* ------------------------------------------------------------------ */
/* boot                                                               */
/* ------------------------------------------------------------------ */

async function init() {
  try {
    const h = await api("/health", {},);
    state.mode = h.mode || "secure";
  } catch (e) { /* backend unreachable; default secure */ }

  if (state.mode === "secure") {
    const meta = document.createElement("meta");
    meta.httpEquiv = "Content-Security-Policy";
    meta.content = "default-src 'self'; img-src 'self' data:; style-src 'self'";
    document.head.appendChild(meta);
  }

  if (state.token) {
    try {
      state.user = await api("/api/users/me");
    } catch (e) {
      state.token = null;
      localStorage.removeItem("tc_token");
    }
  }
  bindNav();
  render();
}

function bindNav() {
  nav.addEventListener("click", (ev) => {
    const btn = ev.target.closest("button[data-view]");
    if (!btn) return;
    const v = btn.dataset.view;
    if (v === "logout") {
      state.token = null;
      state.user = null;
      localStorage.removeItem("tc_token");
      state.view = "products";
    } else {
      state.view = v;
    }
    render();
  });
}

/* ------------------------------------------------------------------ */
/* render dispatcher                                                  */
/* ------------------------------------------------------------------ */

function banner() {
  return state.mode === "vulnerable"
    ? '<div class="card" style="border-color:#f87171"><b>Lab mode: VULNERABLE</b> — intentional weaknesses are enabled.</div>'
    : '<div class="card" style="border-color:#4ade80"><b>Secure mode</b> — remediated build.</div>';
}

function render() {
  const adminNavBtn = document.getElementById("admin-nav");
  if (!state.token) {
    nav.classList.add("hidden");
    if (adminNavBtn) adminNavBtn.classList.add("hidden");
    app.innerHTML = authView();
    bindAuthForms();
    return;
  }
  nav.classList.remove("hidden");
  const canAdmin = state.user.role === "ADMIN" || state.mode === "vulnerable";
  if (adminNavBtn) adminNavBtn.classList.toggle("hidden", !canAdmin);

  switch (state.view) {
    case "products": renderProducts(); break;
    case "orders": renderOrders(); break;
    case "profile": renderProfile(); break;
    case "admin": renderAdmin(); break;
    default: state.view = "products"; renderProducts();
  }
}

/* ------------------------------------------------------------------ */
/* auth views                                                         */
/* ------------------------------------------------------------------ */

function authView() {
  return `
    <div class="auth-panel">
      <div class="card">
        <h1>Welcome to TechCorp</h1>
        ${banner()}
        <div class="flash" id="auth-flash"></div>
        <div id="auth-form">
          <label>Username</label>
          <input id="a-username" autocomplete="username" />
          <label>Password</label>
          <input id="a-password" type="password" autocomplete="current-password" />
          <button class="btn" id="a-login">Sign in</button>
          <button class="btn ghost" id="a-register-view">Create account</button>
        </div>
      </div>
    </div>`;
}

function bindAuthForms() {
  const flash = document.getElementById("auth-flash");
  const login = document.getElementById("a-login");
  const registerView = document.getElementById("a-register-view");
  if (!login || !registerView) return;

  login.addEventListener("click", async () => {
    const username = document.getElementById("a-username").value.trim();
    const password = document.getElementById("a-password").value;
    if (!username || !password) { flash.textContent = "Enter username and password."; return; }
    try {
      const res = await api("/api/login", { method: "POST", body: JSON.stringify({ username, password }) });
      state.token = res.access_token;
      localStorage.setItem("tc_token", state.token);
      state.user = await api("/api/users/me");
      toast(`Signed in as ${state.user.username}`);
      render();
    } catch (e) {
      flash.textContent = e.message;
    }
  });

  registerView.addEventListener("click", () => {
    document.getElementById("auth-form").innerHTML = `
      <label>Username</label><input id="r-username" />
      <label>Email</label><input id="r-email" />
      <label>Password (min 8 chars)</label><input id="r-password" type="password" />
      <button class="btn" id="a-register">Create account</button>`;
    document.getElementById("a-register").addEventListener("click", async () => {
      const username = document.getElementById("r-username").value.trim();
      const email = document.getElementById("r-email").value.trim();
      const password = document.getElementById("r-password").value;
      if (!username || !email || !password) { flash.textContent = "Fill all fields."; return; }
      try {
        await api("/api/register", { method: "POST", body: JSON.stringify({ username, email, password }) });
        flash.style.color = "#4ade80";
        flash.textContent = "Account created — sign in.";
      } catch (e) { flash.textContent = e.message; }
    });
  });
}

/* ------------------------------------------------------------------ */
/* product views                                                      */
/* ------------------------------------------------------------------ */

async function renderProducts() {
  app.innerHTML = `<div class="card"><h1>Products</h1>${banner()}
    <div class="row">
      <input id="search-q" placeholder="Search products…" style="flex:1"/>
      <button class="btn" id="search-btn">Search</button>
    </div>
    <div id="product-grid" class="grid"></div>
  </div>`;

  const load = async (q = "") => {
    const path = q ? `/api/products/search?q=${encodeURIComponent(q)}` : "/api/products";
    try {
      state.products = await api(path);
      drawGrid(state.products);
    } catch (e) {
      document.getElementById("product-grid").innerHTML =
        `<div class="card"><span class="error-text">${esc(e.message)}</span></div>`;
    }
  };

  document.getElementById("search-btn").addEventListener("click", () =>
    load(document.getElementById("search-q").value || null));
  document.getElementById("search-q").addEventListener("keydown", (ev) => {
    if (ev.key === "Enter")
      load(document.getElementById("search-q").value || null);
  });

  await load();
}

function drawGrid(products) {
  const grid = document.getElementById("product-grid");
  if (!grid) return;
  if (!products || products.length === 0) {
    grid.innerHTML = '<div class="card muted">No products match.</div>';
    return;
  }
  grid.innerHTML = products.map((p) => `
    <div class="card product" data-id="${p.id}">
      <h2>${esc(p.name)}</h2>
      <div class="small description)" data-desc>placeholder</div>
      <div class="muted small">$${p.price} · stock ${p.stock}</div>
    </div>`).join("");

  grid.querySelectorAll(".product").forEach((card) => {
    const pid = Number(card.dataset.id);
    const product = products.find((p) => p.id === pid);
    const descEl = card.querySelector("[data-desc]");
    inject(descEl, product ? product.description : "");
    card.addEventListener("click", () => {
      state.selectedProduct = product;
      renderProductDetail();
    });
  });
}

function renderProductDetail() {
  const p = state.selectedProduct;
  if (!p) return;
  app.innerHTML = `
    <div class="card">
      <button class="btn ghost" id="back-btn">← Back</button>
      <h1>${esc(p.name)}</h1>
      <div id="desc"></div>
      <div class="muted">Price: $${p.price} · Stock: ${p.stock}</div>
      <a class="btn" href="#" id="order-link">Buy this product</a>
    </div>`;
  inject(document.getElementById("desc"), p.description);
  document.getElementById("back-btn").addEventListener("click", () => {
    state.selectedProduct = null;
    renderProducts();
  });
  document.getElementById("order-link").addEventListener("click", (ev) => {
    ev.preventDefault();
    state.view = "orders";
    render();
  });
}

/* ------------------------------------------------------------------ */
/* orders view                                                        */
/* ------------------------------------------------------------------ */

async function renderOrders() {
  app.innerHTML = `<div class="card"><h1>My Orders</h1>${banner()}
    <div id="order-form-area"></div>
    <div id="orders-list"></div>
  </div>`;

  const sel = state.selectedProduct;
  const products = state.products && state.products.length ? state.products : await api("/api/products");

  const fields = products.map((p) =>
    `<option value="${p.id}">${esc(p.name)} — $${p.price}</option>`).join("");

  const labExtras = state.mode === "vulnerable" ? `
    <label>Unit price override (lab / VULN-007)</label>
    <input id="o-price" type="number" step="0.01" placeholder="e.g. 0.01" />
    <label>Order status override (lab / VULN-007)</label>
    <select id="o-status"><option value="">(default PENDING)</option>
      <option>PENDING</option><option>PAID</option><option>SHIPPED</option>
      <option>COMPLETED</option><option>CANCELLED</option></select>
  ` : "";

  document.getElementById("order-form-area").innerHTML = `
    <h2>Place an order</h2>
    <label>Product</label>
    <select id="o-product">${fields}</select>
    <label>Quantity</label>
    <input id="o-qty" type="number" value="1" min="1" />
    ${labExtras}
    <button class="btn" id="o-submit">Place order</button>`;

  if (sel) document.getElementById("o-product").value = sel.id;

  document.getElementById("o-submit").addEventListener("click", async () => {
    const productId = Number(document.getElementById("o-product").value);
    const quantity = Number(document.getElementById("o-qty").value);
    const body = { items: [{ product_id: productId, quantity }] };
    if (state.mode === "vulnerable") {
      const price = document.getElementById("o-price").value;
      if (price !== "") body.items[0].price = Number(price);
      const st = document.getElementById("o-status").value;
      if (st) body.status = st;
    }
    try {
      const order = await api("/api/orders", { method: "POST", body: JSON.stringify(body) });
      toast(`Order #${order.id} placed — total $${order.total_amount}`);
      loadOrders();
    } catch (e) { toast(e.message); }
  });

  const loadOrders = async () => {
    try {
      const orders = await api("/api/orders");
      const listEl = document.getElementById("orders-list");
      if (!orders || orders.length === 0) {
        listEl.innerHTML = '<div class="muted">No orders yet.</div>';
        return;
      }
      listEl.innerHTML = `<h2>History</h2><table>
        <tr><th>#</th><th>Status</th><th>Total</th><th>Items</th><th></th></tr>
        ${orders.map((o) => `
          <tr>
            <td>${o.id}</td><td>${esc(o.status)}</td><td>$${o.total_amount}</td>
            <td>${o.items.map((i) => `${i.quantity}×p${i.product_id}`).join(", ")}</td>
            <td><a href="#" data-order="${o.id}">view</a></td>
          </tr>`).join("")}
      </table>`;
      listEl.querySelectorAll("a[data-order]").forEach((a) =>
        a.addEventListener("click", (ev) => {
          ev.preventDefault();
          viewOrder(Number(a.dataset.order));
        }));
    } catch (e) { toast(e.message); }
  };

  await loadOrders();
}

async function viewOrder(id) {
  try {
    const o = await api(`/api/orders/${id}`);
    app.innerHTML = `<div class="card">
      <button class="btn ghost" id="back-btn">← Back</button>
      <h1>Order #${o.id}</h1>
      <p class="muted">Status: <b>${esc(o.status)}</b> · Total: <b>$${o.total_amount}</b></p>
      <table><tr><th>Product</th><th>Qty</th><th>Unit</th></tr>
      ${o.items.map((i) => `<tr><td>product #${i.product_id}</td><td>${i.quantity}</td><td>$${i.price}</td></tr>`).join("")}
      </table>
    </div>`;
    document.getElementById("back-btn").addEventListener("click", () => { state.view = "orders"; render(); });
  } catch (e) { toast(e.message); }
}

/* ------------------------------------------------------------------ */
/* profile view                                                       */
/* ------------------------------------------------------------------ */

async function renderProfile() {
  const u = state.user;
  app.innerHTML = `
    <div class="card">
      <h1>Profile</h1>${banner()}
      <p>Username: <b>${esc(u.username)}</b>
         <span class="badge ${u.role}">${esc(u.role)}</span></p>
      <label>Email</label>
      <input id="p-email" value="${esc(u.email)}" />
      <label>Bio (visible to administrators)</label>
      <textarea id="p-bio"></textarea>
      <div class="small muted">Preview:</div>
      <div id="bio-preview" class="card"></div>
      <button class="btn" id="p-save">Save changes</button>
    </div>`;
  document.getElementById("p-bio").value = u.bio;
  inject(document.getElementById("bio-preview"), u.bio); // VULN-005 sink

  document.getElementById("p-bio").addEventListener("input", (e) => {
    inject(document.getElementById("bio-preview"), e.target.value);
  });

  document.getElementById("p-save").addEventListener("click", async () => {
    const email = document.getElementById("p-email").value.trim();
    const bio = document.getElementById("p-bio").value;
    try {
      state.user = await api(`/api/users/${u.id}`, {
        method: "PUT",
        body: JSON.stringify({ email, bio }),
      });
      toast("Profile updated");
      renderProfile();
    } catch (e) { toast(e.message); }
  });
}

/* ------------------------------------------------------------------ */
/* admin view                                                         */
/* ------------------------------------------------------------------ */

async function renderAdmin() {
  const u = state.user;
  app.innerHTML = `<div class="card"><h1>Admin Dashboard</h1>${banner()}
    <p class="muted">Signed in as <b>${esc(u.username)}</b> (${esc(u.role)})</p>
    <div id="admin-tabs" class="row">
      <button class="btn ghost" data-atab="users">Users</button>
      <button class="btn ghost" data-atab="orders">All Orders</button>
      <button class="btn ghost" data-atab="stats">Stats</button>
    </div>
    <div id="admin-content"></div>
  </div>`;

  const tab = (name) => {
    if (name === "users") adminUsers();
    else if (name === "orders") adminOrders();
    else adminStats();
  };

  document.getElementById("admin-tabs").querySelectorAll("button[data-atab]").forEach((b) =>
    b.addEventListener("click", () => tab(b.dataset.atab)));
  tab("users");
}

async function adminUsers() {
  const box = document.getElementById("admin-content");
  box.innerHTML = '<div class="muted">Loading…</div>';
  try {
    const users = await api("/api/admin/users");
    box.innerHTML = `<h2>Users</h2><table>
      <tr><th>ID</th><th>Username</th><th>Role</th><th>Bio</th></tr>
      ${users.map((u) => `
        <tr data-user-row="${u.id}">
          <td>${u.id}</td><td>${esc(u.username)}</td>
          <td><span class="badge ${u.role}">${esc(u.role)}</span></td>
          <td><div class="small" data-u-bio></div></td>
        </tr>`).join("")}
    </table>`;
    users.forEach((u) => {
      const el = box.querySelector(`tr[data-user-row="${u.id}"] [data-u-bio]`);
      if (el) inject(el, u.bio); // VULN-005: stored XSS payload reaches the admin
    });
  } catch (e) {
    box.innerHTML = `<span class="error-text">${esc(e.message)}</span>`;
  }
}

async function adminOrders() {
  const box = document.getElementById("admin-content");
  box.innerHTML = '<div class="muted">Loading…</div>';
  try {
    const orders = await api("/api/admin/orders");
    box.innerHTML = `<h2>All Orders (admin)</h2><table>
      <tr><th>#</th><th>User</th><th>Status</th><th>Total</th></tr>
      ${orders.map((o) => `
        <tr><td>${o.id}</td><td>${o.user_id}</td>
        <td>${esc(o.status)}</td><td>$${o.total_amount}</td></tr>`).join("")}
    </table>`;
  } catch (e) {
    box.innerHTML = `<span class="error-text">${esc(e.message)}</span>`;
  }
}

async function adminStats() {
  const box = document.getElementById("admin-content");
  try {
    const s = await api("/api/admin/stats");
    box.innerHTML = `<h2>Stats</h2>
      <p>Users: <b>${s.users}</b> · Products: <b>${s.products}</b> · Orders: <b>${s.orders}</b></p>
      <p>Total revenue: <b>$${s.total_revenue}</b></p>`;
  } catch (e) {
    box.innerHTML = `<span class="error-text">${esc(e.message)}</span>`;
  }
}

/* ------------------------------------------------------------------ */

init();