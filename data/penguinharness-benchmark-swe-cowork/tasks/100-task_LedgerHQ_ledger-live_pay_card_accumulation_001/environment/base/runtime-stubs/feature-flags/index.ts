export const setOverride = (payload: unknown) => ({ type: 'featureFlags/setOverride', payload });
export const setAllOverrides = (payload: unknown) => ({ type: 'featureFlags/setAllOverrides', payload });
export const featureFlagsOverridesSelector = (state: any) => state?.featureFlags?.overrides ?? {};
