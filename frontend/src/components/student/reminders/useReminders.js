import { useCallback, useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { dismissReminder, getReminders } from "../../../../api";

// Fired when a reminder is closed, so every list showing reminders (the
// sidebar bell, the chat's welcome banner) drops it too.
const CHANGED_EVENT = "reminders-changed";

// The user's open reminders (backend app/domains/reminders), reloaded when
// the page changes so a reminder disappears once its situation is resolved.
export default function useReminders() {
  const location = useLocation();
  const [items, setItems] = useState([]);

  const load = useCallback(() => {
    getReminders()
      .then((data) => setItems(data.items || []))
      .catch((error) => console.error("Unable to load reminders:", error));
  }, []);

  useEffect(() => { load(); }, [load, location.pathname]);
  useEffect(() => {
    window.addEventListener(CHANGED_EVENT, load);
    return () => window.removeEventListener(CHANGED_EVENT, load);
  }, [load]);

  const dismiss = useCallback(async (key) => {
    setItems((current) => current.filter((r) => r.key !== key));
    try {
      await dismissReminder(key);
      window.dispatchEvent(new Event(CHANGED_EVENT));
    } catch (error) {
      console.error("Unable to dismiss the reminder:", error);
      load();
    }
  }, [load]);

  return { items, dismiss };
}

// Where a reminder's action goes: a page, or the chat with a question filled in.
export function reminderTarget(action) {
  if (!action) return null;
  if (action.prompt) return `/app?prompt=${encodeURIComponent(action.prompt)}`;
  return action.to;
}
