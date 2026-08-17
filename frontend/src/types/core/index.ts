import { CreanovaAction } from "./actions";
import { CreanovaObservation } from "./observations";
import { CreanovaVariance } from "./variances";

/**
 * @deprecated Will be removed once we fully transition to v1 events
 */
export type CreanovaParsedEvent =
  | CreanovaAction
  | CreanovaObservation
  | CreanovaVariance;
