import React from "react";

export function parseInlineMarkdown(text: string): React.ReactNode[] {
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g);
  return parts.map((part, index) => {
    const key = `inline-${index}-${part.slice(0, 8)}`;
    if (part.startsWith("**") && part.endsWith("**")) {
      return <strong key={key} className="font-extrabold text-primary">{part.slice(2, -2)}</strong>;
    }
    if (part.startsWith("`") && part.endsWith("`")) {
      return <code key={key} className="px-1.5 py-0.5 bg-neutral/80 border border-border/20 rounded font-mono text-[11px] text-tertiary">{part.slice(1, -1)}</code>;
    }
    return part;
  });
}

export function formatMarkdown(rawText: string): React.ReactNode {
  if (!rawText) return "";

  // Decode HTML entities that the backend might have pre-encoded
  const text = rawText
    .replace(/&#039;/g, "'")
    .replace(/&#39;/g, "'")
    .replace(/&quot;/g, '"')
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>');

  // Split by code blocks first to isolate them in a ReDoS-safe manner
  const parts = text.split(/(```[a-z]*\n[\s\S]*?\n```)/g);

  return parts.map((part, index) => {
    const blockKey = `block-${index}`;
    if (part.startsWith("```")) {
      const match = part.match(/```([a-z]*)\n([\s\S]*?)\n```/);
      const code = match ? match[2] : part.slice(3, -3);

      return (
        <pre key={blockKey} className="bg-neutral/40 border border-border/20 rounded-lg p-3.5 my-3.5 font-mono text-[11px] text-primary overflow-x-auto max-w-full">
          <code className="block whitespace-pre">{code}</code>
        </pre>
      );
    }

    const lines = part.split("\n");
    const elements: React.ReactNode[] = [];
    let listItems: string[] = [];

    const flushList = (keyPrefix: number) => {
      if (listItems.length > 0) {
        elements.push(
          <ul key={`list-${keyPrefix}`} className="list-disc pl-5 my-2 flex flex-col gap-1">
            {listItems.map((item, idx) => (
              <li key={`li-${keyPrefix}-${idx}`} className="text-sm text-primary/80 font-sans leading-relaxed">
                {parseInlineMarkdown(item)}
              </li>
            ))}
          </ul>
        );
        listItems = [];
      }
    };

    lines.forEach((line, lineIdx) => {
      const trimmed = line.trim();

      if (trimmed.startsWith("### ")) {
        flushList(lineIdx);
        elements.push(
          <h4 key={`h4-${lineIdx}`} className="text-base font-normal italic text-tertiary mt-6 mb-2.5 font-heading">
            {parseInlineMarkdown(trimmed.slice(4))}
          </h4>
        );
      } else if (trimmed.startsWith("## ")) {
        flushList(lineIdx);
        elements.push(
          <h3 key={`h3-${lineIdx}`} className="text-xl font-semibold tracking-normal text-primary/95 mt-8 mb-3.5 font-heading">
            {parseInlineMarkdown(trimmed.slice(3))}
          </h3>
        );
      } else if (trimmed.startsWith("# ")) {
        flushList(lineIdx);
        elements.push(
          <h2 key={`h2-${lineIdx}`} className="text-2xl font-bold tracking-tight text-primary mt-9 mb-4 font-heading">
            {parseInlineMarkdown(trimmed.slice(2))}
          </h2>
        );
      } else if (/^(-{3,}|\*{3,}|_{3,})$/.test(trimmed)) {
        flushList(lineIdx);
        elements.push(
          <hr key={`hr-${lineIdx}`} className="my-4 border-0 border-t border-border/30" />
        );
      } else if (trimmed.startsWith("> ")) {
        flushList(lineIdx);
        elements.push(
          <blockquote key={`bq-${lineIdx}`} className="border-l-2 border-tertiary/40 pl-3 my-2 text-sm text-primary/70 italic leading-relaxed">
            {parseInlineMarkdown(trimmed.slice(2))}
          </blockquote>
        );
      } else if (trimmed.startsWith("- ") || trimmed.startsWith("* ")) {
        listItems.push(trimmed.slice(2));
      } else if (trimmed === "") {
        flushList(lineIdx);
      } else {
        flushList(lineIdx);
        elements.push(
          <p key={`p-${lineIdx}`} className="text-sm text-primary/85 leading-relaxed font-sans mb-2.5 last:mb-0">
            {parseInlineMarkdown(line)}
          </p>
        );
      }
    });

    flushList(lines.length);
    return <React.Fragment key={blockKey}>{elements}</React.Fragment>;
  });
}
