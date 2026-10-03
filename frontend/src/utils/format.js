// Dates and times shown in the app, always in English ("10 Aug 2026",
// "10 Aug 2026, 14:20") whatever the browser's language, in the viewer's
// local time zone. Built by hand rather than with toLocaleString(): month
// abbreviations differ between browsers' locale data (e.g. "Sep"/"Sept").
// null for a missing or unparseable value.

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

function toDate(value) {
  if (!value) return null;
  const date = value instanceof Date ? value : new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

const pad = (n) => String(n).padStart(2, "0");

export function formatDate(value) {
  const date = toDate(value);
  return date && `${date.getDate()} ${MONTHS[date.getMonth()]} ${date.getFullYear()}`;
}

export function formatTime(value) {
  const date = toDate(value);
  return date && `${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

export function formatDateTime(value) {
  const date = toDate(value);
  return date && `${formatDate(date)}, ${formatTime(date)}`;
}
