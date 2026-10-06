import type { SoireeRoute, SoireeStep } from '@/lib/api';

// A step's price, for the two of them; for a band (Secret Squad, `personnes` > 2), each one's share.
export function formatPrice(step: SoireeStep, personnes = 2) {
  if (step.kind === 'nuit') return `${step.price_estimated ? '≈ ' : 'dès '}${step.price.toFixed(0)} € la nuit`;
  if (step.price === 0) return 'Gratuit';
  const about = step.price_estimated ? '≈ ' : '';
  return personnes > 2 ? `${about}${(step.price / personnes).toFixed(0)} € par personne` : `${about}${step.price.toFixed(0)} € à deux`;
}

// The whole evening's price: "≈ 180 €", or a band's share, "≈ 45 €/pers.".
export function routePrice(route: SoireeRoute) {
  const about = route.price_estimated ? '≈ ' : '';
  const personnes = route.personnes ?? 2;
  return personnes > 2 ? `${about}${(route.price / personnes).toFixed(0)} €/pers.` : `${about}${route.price.toFixed(0)} €`;
}
