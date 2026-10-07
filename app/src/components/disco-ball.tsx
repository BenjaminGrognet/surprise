import { StyleSheet, View } from 'react-native';
import Svg, { ClipPath, Circle, Defs, G, LinearGradient, RadialGradient, Rect, Stop } from 'react-native-svg';

// Secret Squad's jewel, where Secret Date has its emerald: a disco ball, mirror tiles throwing back its neons, cyan
// and fuchsia, and the gold.

// A seeded draw, so the ball is the same on every render and every phone.
function seeded(seed: number) {
  let s = seed;
  return () => (s = (s * 16807) % 2147483647) / 2147483647;
}

const W = 400;
const H = 240;
const TILE = 12;
// From the tiles in the shade to those catching the light: black steel, and often the neons (cyan, gold, fuchsia).
const STEEL = ['#0A0A0C', '#111114', '#18181D', '#202027', '#2A2A33', '#363642'];
const GLINTS = ['#3FE0E6', '#E2BC6E', '#FF2BD6'];

// The card's mirror wall: a grid of tiles, each lit by its distance to a spot at the top right, a few of them flashing.
function tiles() {
  const rand = seeded(11);
  const found: { x: number; y: number; fill: string; opacity: number }[] = [];
  for (let y = 0; y < H; y += TILE) {
    for (let x = 0; x < W; x += TILE) {
      const light = 1 - Math.min(1, Math.hypot((W - x) / W, y / H) / 1.25);
      const shade = Math.max(0, Math.min(0.999, light * 0.8 + (rand() - 0.45) * 0.5));
      // Glints all over, many more under the spot.
      const glint = rand() < 0.05 + light * 0.4;
      found.push({
        x, y,
        fill: glint ? GLINTS[Math.floor(rand() * GLINTS.length)] : STEEL[Math.floor(shade * STEEL.length)],
        opacity: glint ? 0.6 + light * 0.4 : 1,
      });
    }
  }
  return found;
}

const TILES = tiles();

// Behind a band's card: the mirror wall, the cyan neon's gleam at the top right and a fuchsia one at the foot left,
// darkened under the text so it reads.
export function DiscoFacets({ id = 'disco' }: { id?: string }) {
  return (
    <View style={StyleSheet.absoluteFill} pointerEvents="none">
      <Svg width="100%" height="100%" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMid slice">
        <Defs>
          <RadialGradient id={`${id}-gleam`} cx="88%" cy="6%" r="80%">
            <Stop offset="0" stopColor="#8FF3F6" stopOpacity={0.7} />
            <Stop offset="0.4" stopColor="#3FE0E6" stopOpacity={0.28} />
            <Stop offset="1" stopColor="#3FE0E6" stopOpacity={0} />
          </RadialGradient>
          <RadialGradient id={`${id}-cold`} cx="4%" cy="100%" r="70%">
            <Stop offset="0" stopColor="#FF2BD6" stopOpacity={0.5} />
            <Stop offset="0.45" stopColor="#FF2BD6" stopOpacity={0.16} />
            <Stop offset="1" stopColor="#FF2BD6" stopOpacity={0} />
          </RadialGradient>
          <LinearGradient id={`${id}-shade`} x1="0" y1="0" x2="0" y2="1">
            <Stop offset="0" stopColor="#0A0A0C" stopOpacity={0.05} />
            <Stop offset="0.45" stopColor="#0A0A0C" stopOpacity={0.5} />
            <Stop offset="1" stopColor="#0A0A0C" stopOpacity={0.75} />
          </LinearGradient>
        </Defs>
        {TILES.map((t, i) => (
          <Rect key={i} x={t.x + 0.6} y={t.y + 0.6} width={TILE - 1.2} height={TILE - 1.2} rx={1.5}
            fill={t.fill} fillOpacity={t.opacity} stroke="#E2BC6E" strokeOpacity={0.12} strokeWidth={0.6} />
        ))}
        <Rect width={W} height={H} fill={`url(#${id}-shade)`} />
        <Rect width={W} height={H} fill={`url(#${id}-gleam)`} />
        <Rect width={W} height={H} fill={`url(#${id}-cold)`} />
      </Svg>
    </View>
  );
}

// The ball itself, as the cards' emblem: rows of tiles, narrower towards the poles, lit from the top left.
const BALL_ROWS = 7;
const BALL = (() => {
  const rand = seeded(5);
  const cells: { x: number; y: number; w: number; h: number; fill: string }[] = [];
  const r = 50;
  for (let row = 0; row < BALL_ROWS; row++) {
    const top = (row / BALL_ROWS) * 100;
    const middle = top + 100 / BALL_ROWS / 2 - r;
    const half = Math.sqrt(Math.max(0, r * r - middle * middle));
    const count = Math.max(3, Math.round((half * 2) / 13));
    for (let i = 0; i < count; i++) {
      const x = r - half + (i * half * 2) / count;
      const light = 1 - Math.hypot(x - 30, top - 25) / 110;
      const glint = rand() < 0.12;
      cells.push({
        x, y: top, w: (half * 2) / count, h: 100 / BALL_ROWS,
        fill: glint ? GLINTS[Math.floor(rand() * 2)] : STEEL[Math.max(0, Math.min(STEEL.length - 1, Math.floor(light * STEEL.length + rand() * 1.5)))],
      });
    }
  }
  return cells;
})();

export function DiscoBall({ size = 30 }: { size?: number }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 100 100" accessibilityLabel="Secret Squad">
      <Defs>
        <ClipPath id="ball">
          <Circle cx={50} cy={50} r={50} />
        </ClipPath>
        <RadialGradient id="ball-light" cx="30%" cy="25%" r="60%">
          <Stop offset="0" stopColor="#FFFFFF" stopOpacity={0.55} />
          <Stop offset="0.5" stopColor="#FFFFFF" stopOpacity={0.05} />
          <Stop offset="1" stopColor="#000000" stopOpacity={0.35} />
        </RadialGradient>
      </Defs>
      <G clipPath="url(#ball)">
        <Rect width={100} height={100} fill="#0A0A0C" />
        {BALL.map((c, i) => (
          <Rect key={i} x={c.x + 0.8} y={c.y + 0.8} width={c.w - 1.6} height={c.h - 1.6} rx={1} fill={c.fill} />
        ))}
        <Circle cx={50} cy={50} r={50} fill="url(#ball-light)" />
      </G>
    </Svg>
  );
}
