/** Tiny, safe Markdown subset parser for briefings: headings, bullets, paragraphs, **bold**, _em_,
 * `code` and [links](https://…). Produces tokens rendered by React (which escapes text), so no HTML
 * from collected content can ever reach the DOM. */
import { safeHref } from "./format";

export type Inline =
  | { t: "text"; v: string } | { t: "b"; v: string } | { t: "i"; v: string } | { t: "code"; v: string }
  | { t: "a"; v: string; href: string };
export type Block = { t: "h"; level: 1 | 2 | 3; c: Inline[] } | { t: "li"; c: Inline[] } | { t: "p"; c: Inline[] };

const INLINE = /\*\*([^*]+)\*\*|_([^_]+)_|`([^`]+)`|\[([^\]]+)\]\(([^)\s]+)\)/g;

export function parseInline(s: string): Inline[] {
  const out: Inline[] = [];
  let last = 0;
  for (const m of s.matchAll(INLINE)) {
    if (m.index! > last) out.push({ t: "text", v: s.slice(last, m.index) });
    if (m[1]) out.push({ t: "b", v: m[1] });
    else if (m[2]) out.push({ t: "i", v: m[2] });
    else if (m[3]) out.push({ t: "code", v: m[3] });
    else {
      const href = safeHref(m[5]);
      if (href) out.push({ t: "a", v: m[4], href });
      else out.push({ t: "text", v: m[4] });
    }
    last = m.index! + m[0].length;
  }
  if (last < s.length) out.push({ t: "text", v: s.slice(last) });
  return out;
}

export function parseMarkdown(md: string): Block[] {
  const blocks: Block[] = [];
  for (const raw of md.split(/\r?\n/)) {
    const line = raw.trimEnd();
    if (!line.trim()) continue;
    const h = /^(#{1,3})\s+(.*)$/.exec(line);
    if (h) { blocks.push({ t: "h", level: h[1].length as 1 | 2 | 3, c: parseInline(h[2]) }); continue; }
    const li = /^\s*[-*]\s+(.*)$/.exec(line);
    if (li) { blocks.push({ t: "li", c: parseInline(li[1]) }); continue; }
    blocks.push({ t: "p", c: parseInline(line) });
  }
  return blocks;
}
