/**
 * Copy plain text to the clipboard.
 *
 * Prefer the Clipboard API; fall back to `document.execCommand("copy")` when
 * the API is missing or blocked (non-secure HTTP contexts, iframe, permissions).
 */
export async function copyTextToClipboard(text: string): Promise<void> {
  try {
    await navigator.clipboard.writeText(text);
    return;
  } catch {
    // Clipboard API is missing or blocked (HTTP, iframe, permissions).
  }

  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.setAttribute("readonly", "");
  textarea.style.position = "fixed";
  textarea.style.top = "0";
  textarea.style.left = "-9999px";
  document.body.appendChild(textarea);
  textarea.select();
  textarea.setSelectionRange(0, textarea.value.length);

  try {
    const copied =
      typeof document.execCommand === "function" &&
      document.execCommand("copy");
    if (!copied) {
      throw new Error("execCommand copy failed");
    }
  } finally {
    textarea.remove();
  }
}
