/** First-message heuristics: VMS analytics need creanova_infra MCP (vms_query). */
const PLATE_RE =
  /(?<![A-Z0-9])(\d{1,3}[A-Z]{1,3}-?\d{3,6})(?![A-Z0-9])/i;
const TRACE_RE = /truy\s*v[ếe]t|l[ịi]ch\s*s[ửu]|bi[ểe]n\s*s[ốo]/i;
const COUNT_RE =
  /([đd][ếe]m|bao\s*nhi[êe]u|s[ốo]\s*xe|lư[ợo]t\s*bi[ểe]n|ra\s*v[àa]o|h[ãa]ng\s*xe|x[âa]m\s*nh[ậa]p|xe\s*m[áa]y)/i;

export function needsInfraMcp(text: string): boolean {
  const t = text.trim();
  if (!t) return false;
  return PLATE_RE.test(t) || TRACE_RE.test(t) || COUNT_RE.test(t);
}
