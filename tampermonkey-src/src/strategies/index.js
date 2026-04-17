/**
 * Strategies module exports
 */

export { BaseStrategy } from './base.js';
export { LocalSignalStrategy } from './localSignal.js';
export { KeltnerMACDStrategy } from './keltnerMACD.js';
export { IQ720EnsembleStrategy } from './iq720Ensemble.js';
export { MomentumBusterStrategy } from './momentumBuster.js';
export { HollyCrossoverStrategy } from './hollyCrossover.js';
export { GoldenOneMomentStrategy } from './goldenOneMoment.js';
export { EMA20PullbackReversalStrategy } from './ema20PullbackReversal.js';
export { strategyManager } from './manager.js';

export default strategyManager;
