export function toCents(value: string | number | null | undefined): number | null {
  if (value === null || value === undefined) return null
  const text = String(value).trim()
  if (!/^\d+(\.\d{1,2})?$/.test(text)) return null
  const [whole, fraction = ''] = text.split('.')
  return Number(whole) * 100 + Number(fraction.padEnd(2, '0'))
}

export function centsToAmount(cents: number): string {
  return (cents / 100).toFixed(2)
}

export function quoteTotalCents(charges: (string | number | null | undefined)[]): number | null {
  let total = 0
  for (const charge of charges) {
    const cents = toCents(charge)
    if (cents === null) return null
    total += cents
  }
  return total
}

export function beatsOwnBest(totalCents: number, currentBest: string | null | undefined): boolean {
  if (!currentBest) return true
  const bestCents = toCents(currentBest)
  return bestCents === null || totalCents < bestCents
}
