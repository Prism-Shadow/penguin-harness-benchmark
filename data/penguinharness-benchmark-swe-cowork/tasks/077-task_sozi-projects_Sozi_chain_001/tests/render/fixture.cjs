'use strict';

function createPresentation(load, specification) {
  load('svg/index');
  const {SVGDocumentWrapper} = load('svg/SVGDocumentWrapper');
  const {Presentation} = load('model/Presentation');
  const svg = SVGDocumentWrapper.fromString(specification.svg);
  if (!svg.isValidSVG) throw new Error('Invalid verifier SVG fixture');
  document.body.innerHTML = '';
  document.body.appendChild(svg.root);
  const presentation = new Presentation();
  presentation.setSVGDocument(svg);
  presentation.fromStorable(specification.presentation);
  Object.assign(presentation, specification.options);
  return {presentation, svg};
}

module.exports = {createPresentation};
