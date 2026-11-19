import type { ErrorBoundaryProps } from '@stoplight/react-error-boundary';
import type { Meta, Story } from '@storybook/react';
import * as React from 'react';

type DocsProps = { data: unknown } & ErrorBoundaryProps;

// Bind the component to the same P accepted by this factory. Storybook's
// conditional component inference cannot reduce an unconstrained generic P.
type DocsComponentMeta<P> = Omit<Meta<React.ComponentType<P>>, 'component'> & {
  component: React.ComponentType<P>;
};

interface HelperReturn<P extends Partial<DocsProps>> {
  meta: DocsComponentMeta<P>;
  createStory(name: string, input: Partial<P>): Story<React.ComponentType<P>>;
  createHoistedStory(input: Partial<P>): Story<React.ComponentType<P>>;
}

export const createStoriesForDocsComponent = <P extends Partial<DocsProps> = DocsProps>(
  Component: React.ComponentType<P>,
  title?: string,
): HelperReturn<P> => {
  const createStory = (name: string, input: Partial<P>) => {
    const story: Story<React.ComponentType<P>> = args => React.createElement(Component, args);
    story.args = input;
    story.storyName = name;
    return story;
  };
  return {
    meta: {
      title: `Internal/Docs/${title || Component.displayName}`,
      component: Component,
      argTypes: <HelperReturn<P>['meta']['argTypes']>{
        data: {
          control: { type: 'object' },
        },
        FallbackComponent: { table: { disable: true } },
        recoverableProps: { table: { disable: true } },
      },
    },
    createStory: createStory,
    createHoistedStory: input => createStory(title ?? Component.displayName ?? Component.name ?? '_unknown_', input),
  };
};
