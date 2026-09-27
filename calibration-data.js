/*
 * Bundled community calibration data.
 *
 * Each entry is a real, user-submitted "what actually happened" report
 * (rank, category, quota, tier, course type, round, outcome) exported from
 * someone's browser via the Feedback tab and merged in here by the maintainer
 * between releases. It starts empty — this file only grows as real people
 * contribute real outcomes; nothing here is synthetic.
 *
 * Shape must match the feedback entries created in app.js (see FEEDBACK
 * entry format: { rank, category, pwd, quota, tier, courseType, round,
 * outcome, source, timestamp } ).
 */
const BUNDLED_CALIBRATION = [];
