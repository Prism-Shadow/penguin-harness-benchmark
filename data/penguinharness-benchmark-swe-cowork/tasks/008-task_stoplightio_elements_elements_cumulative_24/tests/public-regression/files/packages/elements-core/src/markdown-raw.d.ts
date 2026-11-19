// Webpack 5's Storybook preset serves ?raw Markdown as source text.
declare module '*.md?raw' {
  const markdown: string;
  export default markdown;
}
