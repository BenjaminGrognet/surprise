// Shared by the client's pages: home (/), questionnaire (/profil) and evening (/soiree).
const $ = (id) => document.getElementById(id);

function h(tag, attrs = {}, ...children) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v == null || v === false) continue;
    if (k.startsWith("on")) el.addEventListener(k.slice(2), v); else el.setAttribute(k, v === true ? "" : v);
  }
  for (const c of children.flat()) if (c != null && c !== false) el.append(c);
  return el;
}

// Local dates: toISOString() would give the UTC day, the day before around midnight.
const isoDay = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
function nextFriday() {
  const d = new Date(); d.setDate(d.getDate() + ((5 - d.getDay() + 7) % 7 || 7));
  return isoDay(d);
}
const longDay = (day) => new Date(`${day}T12:00`).toLocaleDateString("fr-FR", { weekday: "long", day: "numeric", month: "long" });

function dayField(id, value, set) {
  return h("div", { class: "field" }, h("label", { for: id }, "Le jour"),
    h("input", { type: "date", id, min: isoDay(new Date()), value, oninput: (e) => set(e.target.value) }));
}

// The couple's last profile, for the home page to offer it again (only in this browser;
// a signed-in couple's profile also lives in Supabase, see account.js's accountProfile()).
function rememberProfile(answers, profile) { try { localStorage.setItem("surprise.profile", JSON.stringify({ answers, profile })); } catch {} }
function rememberedProfile() { try { return JSON.parse(localStorage.getItem("surprise.profile") || "null"); } catch { return null; } }

const choiceContent = (o) => [h("span", { class: "emoji", "aria-hidden": "true" }, o.emoji), h("span", {}, o.label)];
