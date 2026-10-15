const LOWERCASE_WORDS = new Set([
  'de',
  'da',
  'do',
  'das',
  'dos',
  'e',
  'em',
  'na',
  'no',
  'nas',
  'nos',
  'a',
  'o',
  'as',
  'os',
  'para',
  'por',
  'com',
]);

export function formatTitleCase(text?: string | null): string {
  if (!text) {
    return '';
  }
  const words = text.trim().split(/\s+/);
  if (!words.length || (words.length === 1 && words[0] === '')) {
    return '';
  }

  return words
    .map((word, idx) => {
      const cleaned = word.toLowerCase();
      if (idx > 0 && LOWERCASE_WORDS.has(cleaned)) {
        return cleaned;
      }
      return cleaned.charAt(0).toUpperCase() + cleaned.slice(1);
    })
    .join(' ');
}

