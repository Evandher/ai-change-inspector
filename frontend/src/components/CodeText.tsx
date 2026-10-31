// Display-only highlighting. It never interprets the diff or changes its text/identifiers.
// Multiline strings and language-specific grammar are intentionally not inferred.
export function CodeText({ text, path }: { text: string; path: string }) {
  if (!/\.(py|[cm]?[jt]sx?|json|java|go|rs|c|cpp|h|cs)$/.test(path)) return <>{text}</>
  const parts = text.split(/("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'|\b(?:def|return|if|else|elif|not|raise|for|in|from|import|class|const|let|function|async|await|export|throw|new|true|false|null|None|True|False)\b|\b\d+(?:\.\d+)?\b)/g)
  return <>{parts.map((part, index) => {
    const kind = /^["']/.test(part) ? 'string' : /^\d/.test(part) ? 'number' : index % 2 ? 'keyword' : null
    return kind ? <span key={index} className={`syntax-${kind}`}>{part}</span> : part
  })}</>
}
