import assert from 'node:assert/strict';
const documentModule: any = await import('../../src/mock-doc/document.ts');
const { createDocument } = documentModule.default ?? documentModule;

const document: any = createDocument();
const element: any = document.createElement('x-basic');
document.body.appendChild(element);
assert.equal(element.tagName, 'X-BASIC');
assert.equal(document.body.childNodes.length, 1);
