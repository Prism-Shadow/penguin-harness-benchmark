import type { Mutation, MutationState } from '../packages/query-core/src/index'

type IsAny<T> = 0 extends (1 & T) ? true : false
type IsUnknown<T> = IsAny<T> extends true
  ? false
  : unknown extends T
    ? ([keyof T] extends [never] ? true : false)
    : false
type Assert<T extends true> = T
type _MutationVariablesDefault = Assert<IsUnknown<Mutation['state']['variables']>>
type _MutationStateVariablesDefault = Assert<IsUnknown<MutationState['variables']>>
