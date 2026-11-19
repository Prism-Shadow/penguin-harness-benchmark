import React from "react";
import { act, renderHook } from "@testing-library/react";
import { Provider } from "react-redux";
import { configureStore } from "@reduxjs/toolkit";
import { useFeatureFlagsToolProps } from "./useFeatureFlagsToolProps";

jest.mock("@shared/feature-flags", () => ({
  setOverride: (payload: unknown) => ({ type: "featureFlags/setOverride", payload }),
  setAllOverrides: (payload: unknown) => ({ type: "featureFlags/setAllOverrides", payload }),
  featureFlagsOverridesSelector: (state: { overrides: object }) => state.overrides,
}), { virtual: true });
jest.mock("@features/platform-feature-flags", () => ({
  useFeatureFlags: () => ({ known: { enabled: true } }),
}), { virtual: true });

test("existing feature flag binding reads Redux and dispatches every public edit", () => {
  const actions: { type: string; payload?: unknown }[] = [];
  const store = configureStore({ reducer: (state = { overrides: { existing: { enabled: false } } }) => state,
    middleware: getDefault => getDefault().concat(() => next => action => {
      actions.push(action as { type: string; payload?: unknown }); return next(action);
    }),
  });
  const wrapper = ({ children }: React.PropsWithChildren) => <Provider store={store}>{children}</Provider>;
  const result = renderHook(() => useFeatureFlagsToolProps(), { wrapper });
  expect(result.result.current.overrides).toEqual(store.getState().overrides);
  expect(result.result.current.resolved).toEqual({ known: { enabled: true } });
  act(() => result.result.current.setOverride("known" as never, { enabled: true } as never));
  act(() => result.result.current.clearOverride("known" as never));
  act(() => result.result.current.setAllOverrides({}));
  act(() => result.result.current.clearAllOverrides());
  expect(actions).toEqual([
    { type: "featureFlags/setOverride", payload: { key: "known", value: { enabled: true } } },
    { type: "featureFlags/setOverride", payload: { key: "known", value: undefined } },
    { type: "featureFlags/setAllOverrides", payload: {} },
    { type: "featureFlags/setAllOverrides", payload: {} },
  ]);
  result.unmount();
});
