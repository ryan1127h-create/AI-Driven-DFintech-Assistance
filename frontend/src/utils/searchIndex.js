// Turns the `search_index` outcomes of one save (the backend rebuilds the
// assistant's retrieval text for each edited knowledge row) into the line
// shown after "Saved". "failed" wins: the row is saved but the assistant
// still quotes the old text until it is saved again.
export function searchIndexMessage(outcomes) {
  const values = outcomes.filter(Boolean);
  if (values.includes("failed")) return { tone: "warning", text: "Saved, but the assistant's search text could not be updated. Save again to retry." };
  if (values.includes("updated")) return { tone: "ok", text: "Saved. The assistant now uses the new text." };
  if (values.includes("missing")) return { tone: "ok", text: "Saved. This record has no search text for the assistant to update." };
  return { tone: "ok", text: "Saved just now." };
}
