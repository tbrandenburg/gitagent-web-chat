import assert from 'node:assert/strict';

export const prompt = 'For the general five-day production sample, follow the production topic index and use its canonical overview and shift register, not the compact two-shift regression example. Report total produced, good, rejected, and downtime across all ten shifts, and name the register and overview source paths. Explain whether these are real measurements or suitable for safety decisions. Do not change files or memory.';

export function validate(answer) {
  for (const value of [/79,?860/, /78,?456/, /1,?404/, /257/]) {
    assert.match(answer, value);
  }
  assert.match(answer, /fabricated|fictional|synthetic/i);
  assert.match(answer, /(?:not|unsuitable)[^\n]{0,140}safety/i);
  assert.match(answer, /knowledge\/production\/shift-production-register\.md/);
  assert.match(answer, /knowledge\/production\/production-data-overview\.md/);
  assert.doesNotMatch(answer, /knowledge\/production\/production-line-example\.md/);
}
