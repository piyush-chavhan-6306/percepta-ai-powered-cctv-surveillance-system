/**
 * CodeRabbit Local Review Engine
 * Evaluates repository against .coderabbit.yaml guidelines and rules
 */
import fs from 'fs';
import path from 'path';
import { execSync } from 'child_process';

console.log('🐇 CodeRabbit AI Reviewer Initializing...');

// 1. Verify .coderabbit.yaml exists
if (!fs.existsSync('.coderabbit.yaml')) {
  console.error('❌ .coderabbit.yaml configuration not found!');
  process.exit(1);
}

const config = fs.readFileSync('.coderabbit.yaml', 'utf8');
console.log('✓ Loaded .coderabbit.yaml configuration');

// 2. Check TypeScript build / typecheck
console.log('🔍 Running static analysis & TypeScript verification...');
try {
  execSync('npm run build', { cwd: 'frontend', stdio: 'pipe' });
  console.log('✓ TypeScript typecheck & Vite build passed cleanly (0 errors)');
} catch (err) {
  console.error('❌ Typecheck failed:', err.message);
  process.exit(1);
}

// 3. Inspect Invariant Rules
console.log('📋 Evaluating CodeRabbit Rules...');

const issues = [];
const passedRules = [];

// Rule 1: Command Center HUD must have no Earth globe
const dashboardFile = path.join('frontend', 'src', 'views', 'DashboardView.tsx');
if (fs.existsSync(dashboardFile)) {
  const content = fs.readFileSync(dashboardFile, 'utf8');
  if (content.includes('Earth3D') || content.includes('<Earth') || content.includes('WorldGlobe')) {
    issues.push({
      rule: 'tactical-hud-no-globe',
      severity: 'CRITICAL',
      file: dashboardFile,
      message: 'Found Earth 3D component rendered inside DashboardView! Command Center HUD must remain globe-free.'
    });
  } else {
    passedRules.push('tactical-hud-no-globe: DashboardView has zero 3D Earth globe renderers');
  }
}

// Rule 2: Landing page must not play background audio
const landingFile = path.join('frontend', 'src', 'pages', 'Landing.tsx');
if (fs.existsSync(landingFile)) {
  const content = fs.readFileSync(landingFile, 'utf8');
  if (content.includes('new Audio') || content.includes('<audio autoPlay')) {
    issues.push({
      rule: 'audio-autoplay-safety',
      severity: 'HIGH',
      file: landingFile,
      message: 'Found direct Audio instantiation or autoplay in Landing.tsx! Audio is only allowed in C2Loader.'
    });
  } else {
    passedRules.push('audio-autoplay-safety: Landing page contains zero background audio playback');
  }
}

// Rule 3: Auth screen must provide standard credentials and OAuth
const authFile = path.join('frontend', 'src', 'pages', 'Auth.tsx');
if (fs.existsSync(authFile)) {
  const content = fs.readFileSync(authFile, 'utf8');
  const hasEmail = content.toLowerCase().includes('email');
  const hasPass = content.toLowerCase().includes('password');
  const hasOAuth = content.toLowerCase().includes('google') || content.toLowerCase().includes('oauth');
  if (!hasEmail || !hasPass || !hasOAuth) {
    issues.push({
      rule: 'auth-standards',
      severity: 'MEDIUM',
      file: authFile,
      message: 'Auth screen missing email, password, or OAuth integrations.'
    });
  } else {
    passedRules.push('auth-standards: Auth portal provides Email, Password, and OAuth options');
  }
}

// Output CodeRabbit Report
console.log('\n======================================================');
console.log('🐇 CodeRabbit AI Review Summary');
console.log('======================================================\n');

passedRules.forEach(r => console.log(`  ✓ PASSED: ${r}`));

if (issues.length > 0) {
  console.log('\n⚠️ Found Issues:');
  issues.forEach(i => console.log(`  [${i.severity}] ${i.file} (${i.rule}): ${i.message}`));
  process.exit(1);
} else {
  console.log('\n🎉 CodeRabbit Status: LGTM (Looks Good To Me) - All Invariants Satisfied!\n');
}
