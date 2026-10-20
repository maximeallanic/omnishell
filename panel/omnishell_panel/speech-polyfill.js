// Replacement of the Web Speech API: recognition goes through the Omnishell daemon (local Whisper).
(() => {
  if (window.__ghSpeech) return;
  const instances = new Map();
  let seq = 0;
  const post = (cmd, id) => window.webkit.messageHandlers.speech.postMessage({cmd, id});
  const results = (text) => {
    const alt = {transcript: text, confidence: 1};
    const res = [alt];
    res.isFinal = true;
    res.item = (i) => res[i];
    const list = [res];
    list.item = (i) => list[i];
    return list;
  };
  const EVENTS = ['start', 'audiostart', 'soundstart', 'speechstart', 'speechend', 'soundend', 'audioend',
                  'result', 'nomatch', 'error', 'end'];

  class SpeechRecognition extends EventTarget {
    constructor() {
      super();
      this.lang = '';
      this.continuous = false;
      this.interimResults = false;
      this.maxAlternatives = 1;
      this.grammars = null;
      this._id = 0;
      this._active = false;
      for (const n of EVENTS) this['on' + n] = null;
    }
    _fire(type, extra) {
      const e = new Event(type);
      Object.assign(e, extra || {});
      this.dispatchEvent(e);
      const h = this['on' + type];
      if (typeof h === 'function') h.call(this, e);
    }
    _finish() {
      if (!this._active) return;
      this._active = false;
      instances.delete(this._id);
      this._fire('end');
    }
    start() {
      if (this._active) throw new DOMException('recognition has already started', 'InvalidStateError');
      this._active = true;
      this._id = ++seq;
      instances.set(this._id, this);
      post('start', this._id);
    }
    stop() {
      if (this._active) post('stop', this._id);
    }
    abort() {
      if (!this._active) return;
      post('abort', this._id);
      this._finish();
    }
  }

  window.__ghSpeech = {
    dispatch(id, type, data) {
      const r = instances.get(id);
      if (!r) return;
      if (type === 'end') r._finish();
      else if (type === 'result') r._fire('result', {resultIndex: 0, results: results(data)});
      else if (type === 'error') r._fire('error', {error: data, message: data});
      else r._fire(type);
    },
  };
  for (const name of ['SpeechRecognition', 'webkitSpeechRecognition'])
    Object.defineProperty(window, name, {value: SpeechRecognition, configurable: true, writable: true});
})();
