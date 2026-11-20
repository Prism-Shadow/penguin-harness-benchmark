/* Preserve unresolved custom-property values as jsdom 24.1.3 does. */
const modulePath = require.resolve('jsdom');
const jsdom = require(modulePath);
const OriginalJSDOM = jsdom.JSDOM;

function declaredValue(window, element, property) {
  let value = '';
  for (const sheet of Array.from(window.document.styleSheets || [])) {
    for (const rule of Array.from(sheet.cssRules || [])) {
      if (!rule.selectorText || !element.matches(rule.selectorText)) continue;
      const candidate = rule.style && rule.style.getPropertyValue(property);
      if (candidate) value = candidate.trim();
    }
  }
  return value;
}

class CompatJSDOM extends OriginalJSDOM {
  constructor(...args) {
    super(...args);
    const original = this.window.getComputedStyle.bind(this.window);
    this.window.getComputedStyle = (element, pseudo) => {
      const computed = original(element, pseudo);
      return new Proxy(computed, {
        get(target, property, receiver) {
          if (typeof property === 'string' && property in target && !target[property]) {
            const cssName = property.replace(/[A-Z]/g, (letter) => `-${letter.toLowerCase()}`);
            return declaredValue(element.ownerDocument.defaultView, element, cssName) || target[property];
          }
          return Reflect.get(target, property, receiver);
        },
      });
    };
  }
}

require.cache[modulePath].exports = { ...jsdom, JSDOM: CompatJSDOM };

