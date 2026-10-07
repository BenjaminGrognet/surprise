// app.json, with Firebase's google-services.json once downloaded into app/ (console › Project settings › the Android
// app fr.secretdate.app): Android's FCM token comes with it (src/lib/push.ts). Without it, the build has no push.
const fs = require('node:fs');
const path = require('node:path');

module.exports = ({ config }) =>
  fs.existsSync(path.join(__dirname, 'google-services.json'))
    ? { ...config, android: { ...config.android, googleServicesFile: './google-services.json' } }
    : config;
