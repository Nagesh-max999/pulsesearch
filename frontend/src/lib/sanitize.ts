/**
 * Search snippets can originate from user-uploaded document content (keyword search
 * highlights come from Postgres ts_headline, semantic snippets are raw text). Escape
 * everything, then re-enable only the <b>/</b> highlight tags ts_headline emits, so a
 * document containing "<script>" text can't inject markup into the results page.
 */
export function sanitizeSnippet(raw: string): string {
  const escaped = raw
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");

  return escaped
    .replaceAll("&lt;b&gt;", "<b>")
    .replaceAll("&lt;/b&gt;", "</b>");
}
