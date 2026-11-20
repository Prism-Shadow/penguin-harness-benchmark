// The real generation loop observes all attention, convolution and recurrent
// cache shapes at the session boundary. No private shape helper is required.
await import('../support/hybrid-generation.mjs');
