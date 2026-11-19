import type { OmitKeyof } from '../packages/query-core/src/index'

type Equal<TLeft, TRight> =
  (<T>() => T extends TLeft ? 1 : 2) extends
  (<T>() => T extends TRight ? 1 : 2) ? true : false
type Assert<T extends true> = T
type Source = { id: string; count: number }
type _StrictOmit = Assert<Equal<OmitKeyof<Source, 'count'>, { id: string }>>
type _SafeOmit = Assert<Equal<OmitKeyof<Source, 'count' | 'missing', 'safely'>, { id: string }>>
// @ts-expect-error strict mode rejects keys that are not present on Source
type _InvalidStrictKey = OmitKeyof<Source, 'missing'>
