export function redactSecrets(url: string): string {
  return url.replace(/(\/kommo\/agendamento\/)[^/?#]+/, '$1***');
}
