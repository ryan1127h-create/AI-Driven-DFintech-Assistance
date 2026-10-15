import { getProfile, getProfileDefinitions } from "../../../../api";

// The field dictionary doesn't change while the app is open, so one fetch
// serves every card in the conversation.
let dictionaryPromise = null;

export function loadDictionary() {
  if (!dictionaryPromise) {
    dictionaryPromise = getProfileDefinitions()
      .then((defs) => ({
        definitions: Object.fromEntries(defs.fields.map((d) => [d.field_key, d])),
        refOptions: defs.ref_options || {},
      }))
      .catch((err) => {
        dictionaryPromise = null;
        throw err;
      });
  }
  return dictionaryPromise;
}

// Current values ({field_key: value}) — read fresh, since the user may
// have changed their profile since the conversation started.
export async function loadProfileValues() {
  const profile = await getProfile();
  return Object.fromEntries(Object.entries(profile.fields || {}).map(([key, field]) => [key, field.value]));
}

// The PATCH /profile changes that set `values`. The backend requires the
// main target role to be one of the target role families, so setting it
// also adds it to the families when it isn't there yet.
export function profileChanges(values, current) {
  const changes = { ...values };
  const main = changes.main_target_role;
  if (main) {
    const families = changes.target_role_families ?? current.target_role_families ?? [];
    if (!families.includes(main)) changes.target_role_families = [...families, main];
  }
  return changes;
}
