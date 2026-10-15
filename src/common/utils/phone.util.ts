export function normalizePhone(raw: string | null | undefined): string | null {
  if (!raw) return null;
  let digits = String(raw).replace(/\D/g, '').replace(/^0+/, '');
  if ((digits.length === 12 || digits.length === 13) && digits.startsWith('55')) {
    digits = digits.slice(2);
  }
  return /^[1-9][0-9]{9,10}$/.test(digits) ? digits : null;
}

// Celular brasileiro: o 9º dígito pode faltar em cadastros antigos ou no WhatsApp.
export function phoneVariants(normalized: string): string[] {
  const ddd = normalized.slice(0, 2);
  const rest = normalized.slice(2);
  if (rest.length === 9 && rest.startsWith('9')) {
    return [normalized, ddd + rest.slice(1)];
  }
  if (rest.length === 8 && /^[6-9]/.test(rest)) {
    return [normalized, `${ddd}9${rest}`];
  }
  return [normalized];
}
