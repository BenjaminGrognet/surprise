// Local dates: toISOString() would give the UTC day, the day before around midnight.
export const isoDay = (d: Date) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;

// The day whose evening is under way: until 6 a.m., the night still belongs to the day before.
export const eveningDay = (now: Date) => isoDay(new Date(now.getTime() - 6 * 3_600_000));

export function nextFriday() {
  const d = new Date();
  d.setDate(d.getDate() + ((5 - d.getDay() + 7) % 7 || 7));
  return isoDay(d);
}

export const longDay = (day: string) =>
  new Date(`${day}T12:00`).toLocaleDateString('fr-FR', { weekday: 'long', day: 'numeric', month: 'long' });

// "ven. 2 oct.": a day in a corner, beside a section's title.
export const shortDay = (day: string) =>
  new Date(`${day}T12:00`).toLocaleDateString('fr-FR', { weekday: 'short', day: 'numeric', month: 'short' });

// "Vendredi 16 octobre · 19:30": an evening's day and hour, as a card prints them.
export function eveningWhen(evening: { day: string; start: string }) {
  const day = longDay(evening.day);
  return `${day.charAt(0).toUpperCase()}${day.slice(1)} · ${formatTime(evening.start)}`;
}

// The evening runs on Paris time regardless of the device's own timezone.
export const formatTime = (iso: string) =>
  new Date(iso).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit', timeZone: 'Europe/Paris' });
