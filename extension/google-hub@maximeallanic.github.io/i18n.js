// Translation functions of the extension, set by extension.js at enable (Extension.gettext and Extension.ngettext of
// the "google-hub" domain declared in metadata.json). Modules import them from here and not from the Shell: until
// enable, and in plain gjs (tests/test_logic.js), msgids are shown as they are.
let translate = msgid => msgid;
let translatePlural = (msgid, msgidPlural, n) => n === 1 ? msgid : msgidPlural;

export function setGettext(gettext, ngettext) {
    translate = gettext;
    translatePlural = ngettext;
}

export const _ = msgid => translate(msgid);
export const ngettext = (msgid, msgidPlural, n) => translatePlural(msgid, msgidPlural, n);

// Named placeholders of a translated string: format('Open {url}', {url}). A function replacement, so that "$&" or "$1"
// in a value (a search query) is inserted as it is typed.
export function format(template, values) {
    return template.replace(/\{(\w+)\}/g, (match, key) => key in values ? String(values[key]) : match);
}
