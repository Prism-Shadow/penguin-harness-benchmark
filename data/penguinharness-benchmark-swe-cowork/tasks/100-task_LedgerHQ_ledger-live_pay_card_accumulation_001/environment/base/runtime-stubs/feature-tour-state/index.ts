export const markPayCardFeatureTourSeen = () => ({ type: 'payCardFeatureTour/markPayCardFeatureTourSeen' });
export const resetPayCardFeatureTourSeen = () => ({ type: 'payCardFeatureTour/resetPayCardFeatureTourSeen' });
export const selectPayCardHasSeenFeatureTour = (state: any) =>
  Boolean(state?.payCardFeatureTour?.hasSeenFeatureTour ?? state?.payCard?.hasSeenFeatureTour);
