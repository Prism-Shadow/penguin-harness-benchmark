// Public Jest setup: use the bundled upstream tiny-model fixture without network.
import { env } from '/app/code/packages/transformers/src/env.js';
env.allowRemoteModels = false;
env.localModelPath = '/opt/task-fixtures/';
