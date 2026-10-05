import { useEffect, useState } from 'react';

import { myTastes, saveTaste, votesOf, type Vote } from '@/lib/account';

type Votes = Record<string, Vote>;

const withVote = (votes: Votes, id: string, vote: Vote | null | undefined): Votes => {
  const next = { ...votes };
  if (vote) next[id] = vote;
  else delete next[id];
  return next;
};

// The account's votes on steps, for a page that shows some: read once, changed at a touch (the same vote again
// withdraws it), put back with the reason if Supabase refuses.
export function useTastes() {
  const [votes, setVotes] = useState<Votes>({});
  const [error, setError] = useState('');

  useEffect(() => {
    myTastes().then((rows) => setVotes(votesOf(rows))).catch(() => {});
  }, []);

  const vote = (step: { id: string; title: string }, value: Vote) => {
    const before = votes[step.id];
    const next = before === value ? null : value;
    setVotes((now) => withVote(now, step.id, next));
    setError('');
    saveTaste(step, next).catch((e: Error) => {
      setVotes((now) => withVote(now, step.id, before));
      setError(e.message);
    });
  };

  return { votes, vote, error };
}
