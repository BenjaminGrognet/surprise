// A step's photo, the site's own. One that does not load is asked for again after a moment, then reported to the
// server, which checks it and answers with another (the official site's) or none: the step then shows a picture of
// the app's own, of its kind (lib/step-images), never a blank.
import { useEffect, useState } from 'react';
import { Image, type ImageStyle, type StyleProp } from 'react-native';

import { reportBrokenImage, type SoireeStep } from '@/lib/api';
import { banner, imageUri, RETRY_MS } from '@/lib/step-images';

type Phase = 'first' | 'waiting' | 'again' | 'reporting' | 'other' | 'lost';

export function StepImage({
  step,
  style,
  blurRadius,
}: {
  step: Pick<SoireeStep, 'id' | 'image_url' | 'role' | 'vibes'>;
  style: StyleProp<ImageStyle>;
  blurRadius?: number;
}) {
  const [shown, setShown] = useState({ of: step.image_url, url: step.image_url, phase: 'first' as Phase });
  // Another step, or the same with another image: from the start.
  if (shown.of !== step.image_url) setShown({ of: step.image_url, url: step.image_url, phase: 'first' });
  const { url, phase } = shown;
  const to = (next: Phase, other?: string) => setShown((s) => ({ ...s, phase: next, url: other ?? s.url }));

  useEffect(() => {
    if (phase !== 'waiting') return;
    const timer = setTimeout(() => to('again'), RETRY_MS);
    return () => clearTimeout(timer);
  }, [phase]);

  useEffect(() => {
    if (phase !== 'reporting' || !step.image_url) return;
    let gone = false;
    reportBrokenImage(step.id, step.image_url).then(
      (r) => !gone && (r.image_url && r.image_url !== step.image_url ? to('other', r.image_url) : to('lost')),
      () => !gone && to('lost'),
    );
    return () => {
      gone = true;
    };
  }, [phase, step.id, step.image_url]);

  if (!url || phase === 'lost' || phase === 'waiting' || phase === 'reporting') {
    return <Image testID="image-de-secours" source={banner(step)} blurRadius={blurRadius} style={style} />;
  }
  const failed = () => to(phase === 'first' ? 'waiting' : phase === 'again' ? 'reporting' : 'lost');
  // A new key for each try: the image is asked for anew, not taken from the failed one.
  return <Image key={phase} source={{ uri: imageUri(url) }} onError={failed} blurRadius={blurRadius} style={style} />;
}
