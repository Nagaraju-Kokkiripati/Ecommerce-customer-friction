const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

// Run the actual handlers without a browser or third-party test dependencies.
const elements = {
  'session-id-input': { value: 'session-test' },
  'response-text': { value: 'Please try an alternative payment method.' },
  'response-channel': { value: 'email' },
};
const context = vm.createContext({
  window: {},
  document: {
    addEventListener() {},
    getElementById: id => elements[id],
  },
  console,
});
vm.runInContext(fs.readFileSync(path.join(__dirname, '../frontend/static/js/app.js'), 'utf8'), context);
vm.runInContext(`
  var notices = [];
  var requests = [];
  var mockResult = null;
  showToast = (message, type) => notices.push({ message, type });
  apiFetch = async (url, options) => {
    requests.push({ url, body: JSON.parse(options.body) });
    return mockResult;
  };
`, context);

(async () => {
  await vm.runInContext("approveIntervention('alternate_payment_method', 'email')", context);
  assert.equal(context.notices.at(-1).type, 'error');
  await vm.runInContext('sendResponse()', context);
  assert.equal(context.notices.at(-1).type, 'error');
  assert.equal(context.requests.at(-1).body.message, elements['response-text'].value);
  assert.equal(context.requests.at(-1).body.session_id, 'session-test');
  context.mockResult = { status: 'simulated', trigger_id: 'TRG-test', message: 'Simulated; no message was delivered' };
  await vm.runInContext('sendResponse()', context);
  assert.match(context.notices.at(-1).message, /no message was delivered/);
  elements['response-text'].value = ' ';
  const count = context.requests.length;
  await vm.runInContext('sendResponse()', context);
  assert.equal(context.requests.length, count);
  assert.equal(context.notices.at(-1).type, 'error');
  console.log('Recovery UI checks passed: failure, simulation, payload, empty draft.');
})().catch(error => { console.error(error); process.exitCode = 1; });
