import { forwardRef, useState } from 'react';
import { StyleSheet, TextInput, type TextInputProps } from 'react-native';

import { Fonts, Radius } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';

// A field set in the night like a tile: a gold hairline at rest, emerald once focused.
export const TextField = forwardRef<TextInput, TextInputProps>(function TextField({ style, onFocus, onBlur, ...rest }, ref) {
  const theme = useTheme();
  const [focused, setFocused] = useState(false);
  return (
    <TextInput
      ref={ref}
      placeholderTextColor={theme.textSecondary}
      onFocus={(e) => { setFocused(true); onFocus?.(e); }}
      onBlur={(e) => { setFocused(false); onBlur?.(e); }}
      style={[styles.input, { backgroundColor: theme.backgroundElement, color: theme.text, borderColor: focused ? theme.accent : theme.line }, style]}
      {...rest}
    />
  );
});

const styles = StyleSheet.create({
  // A solid, zero-wide outline: on web the browser's own focus ring (style auto ignores the width) would hide the emerald one.
  input: { fontFamily: Fonts.sans, fontSize: 15, padding: 15, borderRadius: Radius.field, borderWidth: 1, outlineStyle: 'solid', outlineWidth: 0 },
});
