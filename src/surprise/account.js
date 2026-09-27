// Accounts (Supabase Auth, email + password), shared by every page that can show who's
// logged in: the quiz (which then syncs the profile to the account), the evening result
// (to let a couple keep a route in their history) and the account/history pages themselves.
// No server code in between: the browser talks to Supabase directly with its anon key and,
// once signed in, the user's own session; row-level security is what keeps a couple's data
// to themselves.

let configPromise = null;
function supabaseConfig() {
  configPromise ??= fetch("/api/config").then((r) => r.json()).catch(() => ({ supabaseUrl: "", supabaseAnonKey: "" }));
  return configPromise;
}

function getSession() {
  try { return JSON.parse(localStorage.getItem("surprise.session") || "null"); } catch { return null; }
}
function setSession(session) { try { localStorage.setItem("surprise.session", JSON.stringify(session)); } catch {} }
function clearSession() { try { localStorage.removeItem("surprise.session"); } catch {} }
const currentUser = () => getSession()?.user || null;

async function authFetch(path, body) {
  const { supabaseUrl, supabaseAnonKey } = await supabaseConfig();
  if (!supabaseUrl) throw new Error("Compte non configuré pour l'instant.");
  const r = await fetch(`${supabaseUrl}/auth/v1/${path}`, {
    method: "POST", headers: { "Content-Type": "application/json", apikey: supabaseAnonKey }, body: JSON.stringify(body),
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.error_description || data.msg || "La demande a échoué.");
  return data;
}

async function signUp(email, password) {
  const data = await authFetch("signup", { email, password });
  if (data.access_token) setSession({ access_token: data.access_token, refresh_token: data.refresh_token, user: { id: data.user.id, email: data.user.email } });
  return data;
}
async function signIn(email, password) {
  const data = await authFetch("token?grant_type=password", { email, password });
  setSession({ access_token: data.access_token, refresh_token: data.refresh_token, user: { id: data.user.id, email: data.user.email } });
  return data;
}
function signOut() { clearSession(); }

// A REST call to one of our own tables, scoped by row-level security to the signed-in user.
async function supabaseRest(path, options = {}) {
  const { supabaseUrl, supabaseAnonKey } = await supabaseConfig();
  const session = getSession();
  if (!supabaseUrl) throw new Error("Compte non configuré pour l'instant.");
  if (!session) throw new Error("Connectez-vous d'abord.");
  const r = await fetch(`${supabaseUrl}/rest/v1/${path}`, {
    ...options,
    headers: {
      apikey: supabaseAnonKey, Authorization: `Bearer ${session.access_token}`,
      "Content-Type": "application/json", Prefer: options.prefer || "return=representation",
      ...options.headers,
    },
  });
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).message || "La demande a échoué.");
  return r.status === 204 ? null : r.json();
}

// The account's couple profile: one row per user (couple_profiles.user_id), synced whenever
// the quiz is completed while signed in, and read back to prefill it or to show it on /compte.
async function accountProfile() {
  const user = currentUser();
  if (!user) return null;
  const rows = await supabaseRest(`couple_profiles?user_id=eq.${user.id}&select=id,answers,profile`);
  return rows[0] || null;
}
async function saveAccountProfile(answers, profile) {
  const user = currentUser();
  if (!user) return;
  const existing = await accountProfile();
  if (existing) {
    await supabaseRest(`couple_profiles?id=eq.${existing.id}`, { method: "PATCH", body: JSON.stringify({ answers, profile }), prefer: "return=minimal" });
  } else {
    const id = crypto.randomUUID();
    await supabaseRest("couple_profiles", { method: "POST", body: JSON.stringify({ id, user_id: user.id, answers, profile }), prefer: "return=minimal" });
  }
}

// One evening kept in the couple's history: the route they actually picked, among the ones proposed.
async function chooseEvening({ pageName, routeIndex, title, pitch, vibes, day }) {
  const user = currentUser();
  if (!user) throw new Error("Connectez-vous pour la garder dans votre historique.");
  await supabaseRest("soirees_choisies", {
    method: "POST", prefer: "return=minimal",
    body: JSON.stringify({ id: crypto.randomUUID(), user_id: user.id, page_name: pageName, route_index: routeIndex, title, pitch, vibes, day: day || null }),
  });
}
async function eveningsHistory() {
  return supabaseRest("soirees_choisies?select=*&order=chosen_at.desc");
}

// A small "Mon compte" / "Mon historique" nav, dropped into any page; invisible while
// accounts aren't configured on this server, so the rest of the app stays unaffected.
async function renderAccountNav(container) {
  const { supabaseUrl } = await supabaseConfig();
  if (!supabaseUrl) return;
  const user = currentUser();
  container.replaceChildren(
    user ? h("a", { href: "/historique" }, "Mon historique") : "",
    h("a", { href: "/compte" }, user ? "Mon compte" : "Se connecter"),
  );
}
