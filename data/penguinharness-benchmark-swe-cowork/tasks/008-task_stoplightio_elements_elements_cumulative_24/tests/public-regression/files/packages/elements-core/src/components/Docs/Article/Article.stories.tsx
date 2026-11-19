import basic from '../../../__fixtures__/articles/basic.md?raw';
import kitchenSink from '../../../__fixtures__/articles/kitchen-sink.md?raw';
import multipleTryIts from '../../../__fixtures__/articles/multiple-try-its.md?raw';
import { createStoriesForDocsComponent } from '../story-helper';
import { Article } from './index';

const { meta, createStory } = createStoriesForDocsComponent(Article);
export default meta;

export const Basic = createStory('Basic', { data: basic });

export const KitchenSink = createStory('Kitchen Sink', { data: kitchenSink });

export const MultipleTryIts = createStory('Multiple Try Its', { data: multipleTryIts });
