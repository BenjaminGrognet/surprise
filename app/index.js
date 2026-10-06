// The app's entry: Expo Router, and on Android the home-screen widget's task handler, which draws the widget
// without the app (src/widgets/next-evening-android.tsx).
import 'expo-router/entry';
import { Platform } from 'react-native';

if (Platform.OS === 'android') {
  const { registerWidgetTaskHandler } = require('react-native-android-widget');
  const { widgetTaskHandler } = require('./src/widgets/next-evening-android');
  registerWidgetTaskHandler(widgetTaskHandler);
}
