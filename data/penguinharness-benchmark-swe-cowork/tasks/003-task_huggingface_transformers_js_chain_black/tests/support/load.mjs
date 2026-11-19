import path from 'node:path';
import { pathToFileURL } from 'node:url';

const root = process.env.REPO_DIR_OVERRIDE || process.env.REPO_DIR || process.cwd();
export async function load(relative) {
    try {
        return await import(pathToFileURL(path.join(root, relative)).href);
    } catch (error) {
        console.error('TASK_PRODUCTION_LOAD_ERROR', error.name, error.code || '');
        throw error;
    }
}
