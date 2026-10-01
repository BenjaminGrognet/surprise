import { StyleSheet } from 'react-native';
import Svg, { Defs, LinearGradient, Stop, Text as SvgText, G, Filter, FeDropShadow } from 'react-native-svg';

interface LogoProps {
  size?: number;
}

export function LogoSecretDate({ size = 40 }: LogoProps) {
  return (
    <Svg viewBox="0 0 1000 1000" width={size} height={size} style={styles.svg}>
      <Defs>
        <LinearGradient id="gold" x1="0%" y1="0%" x2="100%" y2="100%">
          <Stop offset="0%" stopColor="#fff0ad" />
          <Stop offset="18%" stopColor="#f7cf68" />
          <Stop offset="48%" stopColor="#c98b24" />
          <Stop offset="72%" stopColor="#f4ca5b" />
          <Stop offset="100%" stopColor="#8e5a12" />
        </LinearGradient>
        <Filter id="shadow" x="-30%" y="-30%" width="160%" height="160%">
          <FeDropShadow dx="0" dy="9" stdDeviation="8" floodColor="#000000" floodOpacity="0.55" />
        </Filter>
      </Defs>

      <G filter="url(#shadow)" fontFamily="Georgia, serif" fontWeight="500">
        {/* D, behind */}
        <SvgText
          x="500"
          y="785"
          textAnchor="middle"
          fontSize="720"
          fill="url(#gold)"
          stroke="#6d430d"
          strokeWidth="8"
        >
          D
        </SvgText>

        {/* S, interlaced/front */}
        <SvgText
          x="455"
          y="730"
          textAnchor="middle"
          fontSize="720"
          fill="url(#gold)"
          stroke="#6d430d"
          strokeWidth="8"
        >
          S
        </SvgText>

        {/* subtle highlight */}
        <SvgText
          x="455"
          y="730"
          textAnchor="middle"
          fontSize="720"
          fill="none"
          stroke="#fff1ad"
          strokeOpacity="0.35"
          strokeWidth="2"
        >
          S
        </SvgText>
      </G>
    </Svg>
  );
}

const styles = StyleSheet.create({
  svg: {
    flex: 1,
  },
});
