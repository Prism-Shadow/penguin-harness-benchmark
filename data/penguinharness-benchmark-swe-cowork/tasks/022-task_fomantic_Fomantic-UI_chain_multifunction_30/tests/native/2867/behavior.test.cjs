const test = require('node:test');
const assert = require('node:assert/strict');
const { browserStyles } = require('../../browser_support.cjs');

test('calendar dimensions follow theme overrides in rendered em, px and rem units', async () => {
  let defaultWidth;
  for (const width of [null, '23em', '37em', '220px', '24rem', null]) {
    const [table, root] = await browserStyles('src/definitions/modules/calendar.less',
      '<div class="ui calendar"><table class="ui table day"><tr><td>1</td></tr></table></div>',
      [{selector:'table',properties:['minWidth','fontSize']},{selector:':root',properties:['fontSize']}],
      1024, width ? {'@widthDay':width} : {});
    const amount=parseFloat(width || '18em');
    const unit=(width || '18em').replace(/[\d.]/g,'');
    const expected=amount*(unit==='rem' ? parseFloat(root.fontSize) : unit==='em' ? parseFloat(table.fontSize) : 1);
    const actual=parseFloat(table.minWidth);
    assert.ok(Math.abs(actual-expected)<0.05, `${width || 'default'}: ${actual} vs ${expected}`);
    if(defaultWidth===undefined) defaultWidth=actual;
    if(width===null) assert.equal(actual,defaultWidth,'restoring defaults restores the original rendered width');
  }
});
