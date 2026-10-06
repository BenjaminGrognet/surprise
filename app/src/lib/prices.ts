import type { SoireeRoute, SoireeStep } from '@/lib/api';

// Who pays: a couple, or a band (Secret Squad) of `personnes`, two friends included.
type Party = Pick<SoireeRoute, 'formule' | 'personnes'>;
const band = (party?: Party) => party?.formule === 'squad';

// A step's price, for the two of them; for a band, each one's share.
export function formatPrice(step: SoireeStep, party?: Party) {
  if (step.kind === 'nuit') return `${step.price_estimated ? '≈ ' : 'dès '}${step.price.toFixed(0)} € la nuit`;
  if (step.price === 0) return 'Gratuit';
  const about = step.price_estimated ? '≈ ' : '';
  return band(party) ? `${about}${(step.price / (party!.personnes ?? 2)).toFixed(0)} € par personne` : `${about}${step.price.toFixed(0)} € à deux`;
}

// The whole evening's price: "≈ 180 €", or a band's share, "≈ 45 €/pers.".
export function routePrice(route: SoireeRoute) {
  const about = route.price_estimated ? '≈ ' : '';
  return band(route) ? `${about}${(route.price / (route.personnes ?? 2)).toFixed(0)} €/pers.` : `${about}${route.price.toFixed(0)} €`;
}
