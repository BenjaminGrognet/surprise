// app.json, with Firebase's google-services.json once downloaded into app/ (console › Project settings › the Android
// app fr.secretdate.app): Android's FCM token comes with it (src/lib/push.ts). Without it, the build has no push.
// On EAS's builders, where the file is not (it stays out of Git), the file variable GOOGLE_SERVICES_JSON gives its
// path (docs/deployer.md, the phone app).
const fs = require('node:fs');
const path = require('node:path');

const googleServices = process.env.GOOGLE_SERVICES_JSON
  ?? (fs.existsSync(path.join(__dirname, 'google-services.json')) ? './google-services.json' : null);

module.exports = ({ config }) =>
  googleServices ? { ...config, android: { ...config.android, googleServicesFile: googleServices } } : config;
