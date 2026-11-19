export function exportsOf(namespace) {
  const commonJs = namespace.default;
  return commonJs && (typeof commonJs === 'object' || typeof commonJs === 'function')
    ? { ...commonJs, ...namespace }
    : namespace;
}
