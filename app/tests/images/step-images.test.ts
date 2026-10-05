// What stands in for a step's photo that cannot be shown: a picture of its kind, stored with the app.
import { describe, expect, test } from '@jest/globals';

import { banner, bannerName, imageUri } from '@/lib/step-images';
import { API_URL } from '@/lib/api';

describe('the picture standing in for a step’s photo', () => {
  test('a meal, a drink and a night have theirs, whatever their mood', () => {
    expect(bannerName({ role: 'repas', vibes: ['rire'] })).toBe('epicuriens');
    expect(bannerName({ role: 'verre', vibes: ['creer'] })).toBe('noctambules');
    expect(bannerName({ role: 'nuit', vibes: [] })).toBe('romantiques');
  });

  test('an outing takes the first of its moods that has a picture', () => {
    expect(bannerName({ role: 'sortie', vibes: ['rire', 'romantique'] })).toBe('complices');
    expect(bannerName({ role: 'sortie', vibes: ['inconnue', 'cultiver'] })).toBe('curieux');
    expect(bannerName({ role: 'sortie', vibes: ['frisson'] })).toBe('explorateurs');
    expect(bannerName({ role: 'sortie', vibes: [] })).toBe('romantiques');
  });

  test('every one is an image of the app’s own', () => {
    for (const vibes of [['rire'], ['creer'], ['cultiver'], ['savourer'], ['flaner'], ['fete'], ['insolite'], ['romantique']])
      expect(banner({ role: 'sortie', vibes })).toBeTruthy();
  });
});

test('the server’s own images are asked of it, the sites’ where they are', () => {
  expect(imageUri('/images/abc.jpg')).toBe(`${API_URL}/images/abc.jpg`);
  expect(imageUri('https://media.timeout.com/a.jpg')).toBe('https://media.timeout.com/a.jpg');
});
