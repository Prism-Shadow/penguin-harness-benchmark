import { PayCardSessionSchema, PayCardParamsSchema } from "./schema";
import { payCardSlice, openPayCard, closePayCard } from "./slice";
import { selectPayCardIsOpen, selectPayCardParams } from "./selectors";

describe("retained Pay Card production package", () => {
  test.each(["desktop", "mobile"])("open/replace/close on %s", platform => {
    const initial = payCardSlice.reducer(undefined, { type: "init" });
    const first = { platform, name: "first", path: "/first" };
    const second = { platform, name: "second" };
    const opened = payCardSlice.reducer(initial, openPayCard(first));
    const replaced = payCardSlice.reducer(opened, openPayCard(second));
    const closed = payCardSlice.reducer(replaced, closePayCard());
    expect(selectPayCardIsOpen({ payCard: opened })).toBe(true);
    expect(selectPayCardParams({ payCard: opened })).toEqual(first);
    expect(selectPayCardParams({ payCard: replaced })).toEqual(second);
    expect(selectPayCardIsOpen({ payCard: closed })).toBe(false);
    expect(selectPayCardParams({ payCard: closed })).toBeNull();
    expect(initial).toEqual({ isOpen: false, params: null });
    expect(payCardSlice.reducer(opened, { type: "unrelated" })).toBe(opened);
  });

  test("session schema rejects empty tokens and malformed timestamps", () => {
    const session = { appSessionToken: "session-one", expiresAt: "2031-04-05T06:07:08.000Z" };
    expect(PayCardSessionSchema.parse(session)).toEqual(session);
    expect(PayCardSessionSchema.safeParse({ ...session, appSessionToken: "" }).success).toBe(false);
    expect(PayCardSessionSchema.safeParse({ ...session, expiresAt: "invalid" }).success).toBe(false);
    expect(PayCardParamsSchema.safeParse({ platform: "desktop", name: "card" }).success).toBe(true);
    expect(PayCardParamsSchema.safeParse({ platform: 4, name: "card" }).success).toBe(false);
  });
});
