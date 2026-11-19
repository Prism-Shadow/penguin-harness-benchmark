export const useFeature = (key: string) => key === 'ptxCard' ? { enabled: false } : { enabled: true, params: { card: true } };
