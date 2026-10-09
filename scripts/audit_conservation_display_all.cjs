// Every API conservation payload is checked, not a handpicked species fixture.
const fs = require('node:fs');
const chat = require('../src/robingraph/api/static/chat.js');
const input = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const failures = [], counts = {}, byGrade = {};
for (const {taxon, conservation} of input.species) {
  const info = chat.conservationInfo(conservation, taxon);
  const ref = chat.referenceAssessmentInfo(conservation, taxon);
  const expected = ref ? ref.category : conservation.category;
  if (expected && expected !== 'NE') {
    if (!info.badgeText.includes('(' + expected + ')')) failures.push({taxon, error:'known grade absent from badge', expected, info});
    const palette = expected === 'DD' ? 'unconfirmed' : expected.toLowerCase();
    if (info.tier !== palette) failures.push({taxon, error:'grade colour mismatch', expected, info});
    byGrade[expected] = (byGrade[expected] || 0) + 1;
  }
  if (!info.badgeText.startsWith('IUCN 적색목록')) failures.push({taxon,error:'badge omitted'});
  if (conservation.reference_assessment && !ref) failures.push({taxon,error:'backend reference rejected by frontend'});
  counts[info.tier] = (counts[info.tier] || 0) + 1;
}
console.log(JSON.stringify({method:'all reader payloads through frontend conservationInfo; no browser DOM',species_count:input.species_count,processed:input.species.length,grade_counts:byGrade,tier_counts:counts,failures},null,2));
if(failures.length)process.exitCode=1;
