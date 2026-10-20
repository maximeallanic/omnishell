// Returns 'sent', or the step that failed ('no-composer', 'no-send-button', 'send-disabled') so the caller can log it.
const wait = (ms) => new Promise(r => setTimeout(r, ms));
const t0 = Date.now();
let el;
while (!(el = document.querySelector(COMPOSER))) {
  if (Date.now() - t0 > 3000) return 'no-composer';
  await wait(100);
}
el.focus();
document.execCommand('selectAll', false, null);
document.execCommand('insertText', false, text);
let btn;
while (!(btn = document.querySelector(SEND)) || btn.disabled || btn.getAttribute('aria-disabled') === 'true') {
  if (Date.now() - t0 > 3000) return btn ? 'send-disabled' : 'no-send-button';
  await wait(100);
}
btn.click();
return 'sent';
