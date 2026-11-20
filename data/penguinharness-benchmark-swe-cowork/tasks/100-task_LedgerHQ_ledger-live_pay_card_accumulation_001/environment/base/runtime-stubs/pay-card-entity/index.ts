export const PAY_CARD_BALANCE_FILTER_ALL = 'all';
export const markPayCardFeatureTourSeen = () => ({ type: 'payCard/markPayCardFeatureTourSeen' });
export const resetPayCardFeatureTourSeen = () => ({ type: 'payCard/resetPayCardFeatureTourSeen' });
export const selectPayCardHasSeenFeatureTour = (state: any) =>
  Boolean(state?.payCardFeatureTour?.hasSeenFeatureTour ?? state?.payCard?.hasSeenFeatureTour);
