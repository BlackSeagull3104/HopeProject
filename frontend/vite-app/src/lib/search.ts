export function highlightedParts(text: string, query: string) {
  if (!query) return [{ text, match: false }]
  const lower = text.toLowerCase(),
    needle = query.toLowerCase()
  const parts: { text: string; match: boolean }[] = []
  let position = 0
  let found = lower.indexOf(needle)
  while (found >= 0) {
    if (found > position)
      parts.push({ text: text.slice(position, found), match: false })
    parts.push({ text: text.slice(found, found + query.length), match: true })
    position = found + query.length
    found = lower.indexOf(needle, position)
  }
  if (position < text.length)
    parts.push({ text: text.slice(position), match: false })
  return parts
}
