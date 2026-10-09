// The site's build (npm run build:web → dist, served by surprise.quiz on 8001), with app/.env's variables: made
// again only when the app, its settings or app/.env changed since the last one (WEB_REBUILD=1 to make it anyway).
const { stamp, upToDate, exportWeb } = require('./build-stamp');

const wanted = stamp(process.env, ['.env']);
if (upToDate('dist', wanted) && !process.env.WEB_REBUILD) {
  console.log('dist à jour : le build est repris tel quel (WEB_REBUILD=1 pour le refaire)');
} else {
  exportWeb('dist', process.env, wanted);
}
