// Expo's own (Metro uses it without this file); written out for Jest's babel-jest.
module.exports = function (api) {
  api.cache(true);
  return { presets: ['babel-preset-expo'] };
};
