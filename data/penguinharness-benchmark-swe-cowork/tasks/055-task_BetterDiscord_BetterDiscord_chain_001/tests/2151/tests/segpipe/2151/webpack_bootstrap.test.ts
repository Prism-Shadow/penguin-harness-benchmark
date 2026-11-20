import {expect, mock, test} from "bun:test";

test("webpack bootstrap creates the Discord chunk queue when it is absent", async () => {
    globalThis.requestIdleCallback ??= ((callback: IdleRequestCallback) => {
        callback({didTimeout: false, timeRemaining: () => 50});
        return 1;
    }) as typeof requestIdleCallback;
    (window as any).BetterDiscordPreload = () => ({});

    delete (window as any).webpackChunkdiscord_app;
    const repo = process.env.REPO_DIR ?? process.cwd();

    mock.module(`${repo}/src/betterdiscord/modules/patcher.ts`, () => ({
        default: {after() {}, before() {}, unpatchAll() {}}
    }));
    mock.module(`${repo}/src/betterdiscord/webpack/searching.ts`, () => ({
        getModule: () => undefined
    }));

    await import(`${repo}/src/betterdiscord/webpack/require.ts?strict-pr-2151`);

    expect(Array.isArray((window as any).webpackChunkdiscord_app)).toBe(true);
    expect(typeof (window as any).webpackChunkdiscord_app.push).toBe("function");
});
