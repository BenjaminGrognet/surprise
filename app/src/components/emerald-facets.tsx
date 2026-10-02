import { StyleSheet, View } from 'react-native';
import Svg, { Defs, LinearGradient, Polygon, RadialGradient, Rect, Stop } from 'react-native-svg';

const W = 400;
const H = 240;
const COLS = 7;
const ROWS = 5;
// From the stone's depth to the facets that catch the light.
const RAMP = ['#03150E', '#052117', '#082D1F', '#0C3B29', '#124B34', '#1A5E41', '#247552'];

// A seeded draw, so the stone is cut the same way on every render and every phone.
function seeded(seed: number) {
  let s = seed;
  return () => (s = (s * 16807) % 2147483647) / 2147483647;
}

// A cut emerald: a jittered grid split into triangles, each one lit by its distance to a light at the top right.
function cut() {
  const rand = seeded(7);
  const points: [number, number][][] = [];
  for (let r = 0; r <= ROWS; r++) {
    const row: [number, number][] = [];
    for (let c = 0; c <= COLS; c++) {
      const jx = c === 0 || c === COLS ? 0 : (rand() - 0.5) * (W / COLS) * 0.9;
      const jy = r === 0 || r === ROWS ? 0 : (rand() - 0.5) * (H / ROWS) * 0.9;
      row.push([(c / COLS) * W + jx, (r / ROWS) * H + jy]);
    }
    points.push(row);
  }
  const facets: { points: string; fill: string }[] = [];
  for (let r = 0; r < ROWS; r++) {
    for (let c = 0; c < COLS; c++) {
      const [a, b, d, e] = [points[r][c], points[r][c + 1], points[r + 1][c], points[r + 1][c + 1]];
      const pair = rand() > 0.5 ? [[a, b, e], [a, e, d]] : [[a, b, d], [b, e, d]];
      for (const tri of pair) {
        const cx = (tri[0][0] + tri[1][0] + tri[2][0]) / 3;
        const cy = (tri[0][1] + tri[1][1] + tri[2][1]) / 3;
        const light = 1 - Math.min(1, Math.hypot((W - cx) / W, cy / H) / 1.2);
        const shade = Math.max(0, Math.min(0.999, light * 0.85 + (rand() - 0.45) * 0.45));
        facets.push({ points: tri.map((p) => p.join(',')).join(' '), fill: RAMP[Math.floor(shade * RAMP.length)] });
      }
    }
  }
  return facets;
}

const FACETS = cut();

// The membership card's stone: faceted emerald, a gleam at the top right, darkened at the foot so the text reads.
export function EmeraldFacets({ id = 'stone' }: { id?: string }) {
  return (
    // Sized by its frame, not by its viewBox: on web an Svg left to itself keeps the viewBox's proportions.
    <View style={StyleSheet.absoluteFill} pointerEvents="none">
      <Svg width="100%" height="100%" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMid slice">
        <Defs>
          <RadialGradient id={`${id}-gleam`} cx="88%" cy="6%" r="70%">
            <Stop offset="0" stopColor="#9FF2CB" stopOpacity={0.3} />
            <Stop offset="0.45" stopColor="#3DB787" stopOpacity={0.08} />
            <Stop offset="1" stopColor="#3DB787" stopOpacity={0} />
          </RadialGradient>
          <LinearGradient id={`${id}-shade`} x1="0" y1="0" x2="0" y2="1">
            <Stop offset="0" stopColor="#020B07" stopOpacity={0.15} />
            <Stop offset="0.55" stopColor="#020B07" stopOpacity={0.45} />
            <Stop offset="1" stopColor="#020B07" stopOpacity={0.82} />
          </LinearGradient>
        </Defs>
        {FACETS.map((f, i) => (
          <Polygon key={i} points={f.points} fill={f.fill} stroke="#7FE0B4" strokeOpacity={0.07} strokeWidth={0.7} />
        ))}
        {/* Two pale shards catching the light, like the crystal tips of the reference card. */}
        <Polygon points="0,0 34,0 12,58" fill="#DDEFE6" fillOpacity={0.08} />
        <Polygon points="400,0 352,0 384,92" fill="#DDEFE6" fillOpacity={0.1} />
        <Rect width={W} height={H} fill={`url(#${id}-gleam)`} />
        <Rect width={W} height={H} fill={`url(#${id}-shade)`} />
      </Svg>
    </View>
  );
}
