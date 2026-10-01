import { useState } from 'react';
import { StyleSheet, TextInput, type TextInputProps } from 'react-native';

import { Fonts } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';

// A see-through field over the night: a faint champagne border that lights up fully on focus.
export function TextField({ style, onFocus, onBlur, ...rest }: TextInputProps) {
  const theme = useTheme();
  const [focused, setFocused] = useState(false);
  return (
    <TextInput
      placeholderTextColor={theme.textSecondary}
      onFocus={(e) => { setFocused(true); onFocus?.(e); }}
      onBlur={(e) => { setFocused(false); onBlur?.(e); }}
      style={[styles.input, { backgroundColor: theme.glass, color: theme.text, borderColor: focused ? theme.accent : theme.accentFaint }, style]}
      {...rest}
    />
  );
}

const styles = StyleSheet.create({
  // A solid, zero-wide outline: on web the browser's own focus ring (style auto ignores the width) would hide the gold one.
  input: { fontFamily: Fonts.sans, fontSize: 16, padding: 14, borderRadius: 14, borderWidth: 1, outlineStyle: 'solid', outlineWidth: 0 },
});
