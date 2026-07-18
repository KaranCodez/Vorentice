"use client";

import React from "react";

/* A focused Markdown renderer for the Risk Agent chat — supports headers,
 * bold / italic / inline-code, bullet & numbered lists, GFM tables,
 * blockquotes and horizontal rules. Zero dependencies, streaming-safe
 * (re-parses the full string on every token). */

type Node = React.ReactNode;

/* ── inline: **bold**, *italic*, `code` ── */
function renderInline(text: string, keyPrefix: string): Node[] {
  const nodes: Node[] = [];
  const regex = /(\*\*([^*]+)\*\*|`([^`]+)`|\*([^*]+)\*)/g;
  let last = 0;
  let m: RegExpExecArray | null;
  let i = 0;
  while ((m = regex.exec(text)) !== null) {
    if (m.index > last) nodes.push(text.slice(last, m.index));
    const key = `${keyPrefix}-i${i++}`;
    if (m[2] !== undefined) {
      nodes.push(
        <strong key={key} className="font-semibold text-white">
          {m[2]}
        </strong>
      );
    } else if (m[3] !== undefined) {
      nodes.push(
        <code
          key={key}
          className="rounded bg-white/10 px-1.5 py-0.5 font-mono text-[0.85em] text-orange-200"
        >
          {m[3]}
        </code>
      );
    } else if (m[4] !== undefined) {
      nodes.push(
        <em key={key} className="italic text-white/90">
          {m[4]}
        </em>
      );
    }
    last = m.index + m[0].length;
  }
  if (last < text.length) nodes.push(text.slice(last));
  return nodes;
}

interface Block {
  type: "h1" | "h2" | "h3" | "ul" | "ol" | "table" | "hr" | "quote" | "p";
  lines?: string[];
  text?: string;
  rows?: string[][];
  align?: ("left" | "center" | "right")[];
}

function splitRow(line: string): string[] {
  const trimmed = line.trim().replace(/^\|/, "").replace(/\|$/, "");
  return trimmed.split("|").map((c) => c.trim());
}

function parseBlocks(md: string): Block[] {
  const lines = md.replace(/\r\n/g, "\n").split("\n");
  const blocks: Block[] = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];
    const t = line.trim();

    if (t === "") {
      i++;
      continue;
    }

    // horizontal rule
    if (/^(-{3,}|_{3,}|\*{3,})$/.test(t)) {
      blocks.push({ type: "hr" });
      i++;
      continue;
    }

    // headers
    const h = /^(#{1,3})\s+(.*)$/.exec(t);
    if (h) {
      const level = h[1].length;
      blocks.push({
        type: level === 1 ? "h1" : level === 2 ? "h2" : "h3",
        text: h[2],
      });
      i++;
      continue;
    }

    // table: current line has |, next line is a separator row
    if (t.includes("|") && i + 1 < lines.length && /^\s*\|?[\s:|-]+\|?\s*$/.test(lines[i + 1]) && lines[i + 1].includes("-")) {
      const header = splitRow(t);
      const align = splitRow(lines[i + 1]).map((c) => {
        const l = c.startsWith(":");
        const r = c.endsWith(":");
        return l && r ? "center" : r ? "right" : "left";
      }) as ("left" | "center" | "right")[];
      const rows: string[][] = [header];
      i += 2;
      while (i < lines.length && lines[i].trim().includes("|") && lines[i].trim() !== "") {
        rows.push(splitRow(lines[i]));
        i++;
      }
      blocks.push({ type: "table", rows, align });
      continue;
    }

    // blockquote
    if (/^>\s?/.test(t)) {
      const quote: string[] = [];
      while (i < lines.length && /^>\s?/.test(lines[i].trim())) {
        quote.push(lines[i].trim().replace(/^>\s?/, ""));
        i++;
      }
      blocks.push({ type: "quote", lines: quote });
      continue;
    }

    // unordered list
    if (/^[-*+]\s+/.test(t)) {
      const items: string[] = [];
      while (i < lines.length && /^[-*+]\s+/.test(lines[i].trim())) {
        items.push(lines[i].trim().replace(/^[-*+]\s+/, ""));
        i++;
      }
      blocks.push({ type: "ul", lines: items });
      continue;
    }

    // ordered list
    if (/^\d+[.)]\s+/.test(t)) {
      const items: string[] = [];
      while (i < lines.length && /^\d+[.)]\s+/.test(lines[i].trim())) {
        items.push(lines[i].trim().replace(/^\d+[.)]\s+/, ""));
        i++;
      }
      blocks.push({ type: "ol", lines: items });
      continue;
    }

    // paragraph (consume until blank or block-start)
    const para: string[] = [];
    while (
      i < lines.length &&
      lines[i].trim() !== "" &&
      !/^(#{1,3}\s|[-*+]\s|\d+[.)]\s|>\s?|-{3,}$|_{3,}$)/.test(lines[i].trim())
    ) {
      para.push(lines[i].trim());
      i++;
    }
    blocks.push({ type: "p", text: para.join(" ") });
  }

  return blocks;
}

export default function Markdown({ text }: { text: string }) {
  const blocks = parseBlocks(text);

  return (
    <div className="risk-md flex flex-col gap-2.5 text-[13.5px] leading-relaxed text-white/85">
      {blocks.map((b, idx) => {
        const key = `b${idx}`;
        switch (b.type) {
          case "h1":
            return (
              <h1 key={key} className="mt-1 text-base font-bold text-white">
                {renderInline(b.text!, key)}
              </h1>
            );
          case "h2":
            return (
              <h2
                key={key}
                className="mt-2 flex items-center gap-2 text-[14px] font-bold text-orange-300"
              >
                <span className="h-3 w-0.5 rounded bg-orange-400/70" />
                {renderInline(b.text!, key)}
              </h2>
            );
          case "h3":
            return (
              <h3 key={key} className="mt-1 text-[13px] font-semibold text-white/95">
                {renderInline(b.text!, key)}
              </h3>
            );
          case "hr":
            return <hr key={key} className="my-1 border-white/10" />;
          case "ul":
            return (
              <ul key={key} className="flex flex-col gap-1.5 pl-1">
                {b.lines!.map((li, j) => (
                  <li key={j} className="flex gap-2">
                    <span className="mt-[7px] size-1.5 shrink-0 rounded-full bg-orange-400/80" />
                    <span>{renderInline(li, `${key}-${j}`)}</span>
                  </li>
                ))}
              </ul>
            );
          case "ol":
            return (
              <ol key={key} className="flex flex-col gap-1.5 pl-1">
                {b.lines!.map((li, j) => (
                  <li key={j} className="flex gap-2.5">
                    <span className="mt-px flex size-4 shrink-0 items-center justify-center rounded bg-orange-500/20 font-mono text-[10px] font-semibold text-orange-300">
                      {j + 1}
                    </span>
                    <span>{renderInline(li, `${key}-${j}`)}</span>
                  </li>
                ))}
              </ol>
            );
          case "quote":
            return (
              <blockquote
                key={key}
                className="rounded-r-lg border-l-2 border-orange-400/70 bg-orange-500/[0.07] px-3 py-2 text-white/80"
              >
                {b.lines!.map((l, j) => (
                  <div key={j}>{renderInline(l, `${key}-${j}`)}</div>
                ))}
              </blockquote>
            );
          case "table":
            return (
              <div key={key} className="my-1 overflow-x-auto">
                <table className="w-full border-collapse text-[12.5px]">
                  <thead>
                    <tr>
                      {b.rows![0].map((cell, c) => (
                        <th
                          key={c}
                          className="border-b border-white/15 bg-white/[0.04] px-3 py-2 text-left font-semibold text-orange-200"
                          style={{ textAlign: b.align?.[c] ?? "left" }}
                        >
                          {renderInline(cell, `${key}-h${c}`)}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {b.rows!.slice(1).map((row, r) => (
                      <tr key={r} className="even:bg-white/[0.02]">
                        {row.map((cell, c) => (
                          <td
                            key={c}
                            className="border-b border-white/[0.06] px-3 py-2 align-top text-white/80"
                            style={{ textAlign: b.align?.[c] ?? "left" }}
                          >
                            {renderInline(cell, `${key}-${r}-${c}`)}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            );
          default:
            return (
              <p key={key} className="text-white/85">
                {renderInline(b.text!, key)}
              </p>
            );
        }
      })}
    </div>
  );
}
