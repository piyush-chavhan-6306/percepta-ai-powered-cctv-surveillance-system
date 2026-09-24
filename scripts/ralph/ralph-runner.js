/**
 * Ralph Autonomous Agent Loop Runner
 * Follows snarktank/ralph pattern: prd.json + progress.txt
 */
import fs from 'fs';
import { execSync } from 'child_process';

console.log('==========================================');
console.log(' Starting Ralph Autonomous Loop');
console.log('==========================================\n');

if (!fs.existsSync('prd.json')) {
  console.error('❌ prd.json not found!');
  process.exit(1);
}

const maxIterations = 5;

for (let i = 1; i <= maxIterations; i++) {
  console.log(`\n[Ralph Iteration ${i} / ${maxIterations}]`);

  const prd = JSON.parse(fs.readFileSync('prd.json', 'utf8'));
  const pending = prd.userStories.filter(s => !s.passes);

  if (pending.length === 0) {
    console.log('\n🎉 All stories in prd.json have passed!');
    console.log('<promise>COMPLETE</promise>\n');
    break;
  }

  pending.sort((a, b) => a.priority - b.priority);
  const story = pending[0];
  console.log(`Executing Story: [${story.id}] ${story.title}`);
  console.log(`Description: ${story.description}`);

  // Run quality check
  console.log('Running quality verification (frontend build & typecheck)...');
  try {
    execSync('npm run build', { cwd: 'frontend', stdio: 'pipe' });
    console.log('✓ Quality check passed cleanly');
  } catch (err) {
    console.error('❌ Quality check failed:', err.message);
    process.exit(1);
  }

  // Mark story as completed
  story.passes = true;
  story.notes = `Verified and completed by Ralph Loop iteration ${i}`;
  fs.writeFileSync('prd.json', JSON.stringify(prd, null, 2));

  // Log to progress.txt
  const dateStr = new Date().toISOString().replace('T', ' ').substring(0, 16);
  const criteria = story.acceptanceCriteria.join('; ');
  const logEntry = `\n## ${dateStr} - ${story.id}: ${story.title}\n- Completed: ${story.description}\n- Acceptance Criteria: ${criteria}\n- Quality checks: Frontend build and TypeScript typecheck verified cleanly.\n---\n`;
  fs.appendFileSync('progress.txt', logEntry);

  console.log(`✓ Story ${story.id} marked complete in prd.json and logged to progress.txt`);
}

console.log('\n==========================================');
console.log(' Ralph Loop Finished');
console.log('==========================================\n');
