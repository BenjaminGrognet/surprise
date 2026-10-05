// Le Livre des Secrets: each one seals a page of a kept evening, and reads the other's once their own is sealed.
import { expect, test } from '@jest/globals';
import { eveningsHistory } from '@/lib/account';
import { joinEvening } from '@/lib/couple';
import { book, sealPage } from '@/lib/souvenirs';

import { as, keep, newAccount, PAST, PHOTO } from './helpers';

test("each one seals a page; the other's reads only once one's own is sealed", async () => {
  const lea = await newAccount('instigatrice');
  const row = await keep(PAST);
  const sam = await newAccount('passager');
  await joinEvening(row.invite_code);

  await as(lea);
  await sealPage(row.id, '  Le meilleur soir de l’année.  ', PHOTO);
  await expect(sealPage(row.id, 'Encore', null)).rejects.toThrow('Votre page est déjà scellée.');
  const mine = await book(row.page_name);
  expect(mine?.pages).toHaveLength(1);
  expect(mine?.pages[0]).toMatchObject({ author: lea.id, note: 'Le meilleur soir de l’année.', mine: true });
  expect(mine?.pages[0].photo).toMatch(new RegExp(`^${row.id}/${lea.id}/\\d+\\.png$`));
  const photo = await fetch(mine!.pages[0].photoUrl!);
  expect(photo.status).toBe(200);

  await as(sam);
  expect((await book(row.page_name))?.pages).toEqual([]);
  expect((await eveningsHistory())[0].souvenirs).toEqual([]);
  await sealPage(row.id, 'Merci', null);
  const both = await book(row.page_name);
  expect(both?.pages.map((p) => [p.author, p.mine])).toEqual([[sam.id, true], [lea.id, false]]);
  expect(both?.pages[1].photoUrl).toBeTruthy();
  expect((await eveningsHistory())[0].souvenirs).toHaveLength(2);
});

test('an account outside the evening neither seals a page nor drops a photo in it', async () => {
  await newAccount('instigateur');
  const row = await keep(PAST);
  await newAccount('intrus');
  expect(await book(row.page_name)).toBeNull();
  await expect(sealPage(row.id, 'Je n’y étais pas', null)).rejects.toThrow();
  await expect(sealPage(row.id, '', PHOTO)).rejects.toThrow("La photo n'a pas pu être déposée");
});
