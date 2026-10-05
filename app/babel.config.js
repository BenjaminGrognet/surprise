// Expo's own (Metro uses it without this file); written out for Jest's babel-jest, where the app's lazy imports
// (`await import(…)`, as lib/notifications.ts loads expo-notifications) become requires: Jest runs CommonJS.
module.exports = function (api) {
  const jest = api.env('test');
  return { presets: ['babel-preset-expo'], plugins: jest ? ['@babel/plugin-transform-dynamic-import'] : [] };
};
