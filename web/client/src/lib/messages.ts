// What the page says when the server couldn't be reached for something: one sentence each, kept here so their
// wording is read in one place (layers.test.ts keeps "Couldn't …" out of every other file). A refusal the server
// explains is said in its own words instead (api.ts, plainError); these are for when there are none.
export const SAID = {
  unreachable: "Couldn't reach the server.",
  notSaved: "That didn't save. Try again.",

  // loading
  coaches: "Couldn't load your coaches.",
  level: "Couldn't load your level.",
  feed: "Couldn't load your podcast link.",
  workouts: "Couldn't load your workouts.",
  books: "Couldn't load the books.",
  script: "Couldn't load the script. Try again.",
  minutes: "Couldn't load your minutes.",

  // saving
  coach: "That coach couldn't be chosen just now. Try again.",
  sky: "That background didn't save. Try again.",
  levelNotSaved: "Couldn't save your level. Try again.",
  link: "Couldn't make a link. Try again.",
  qr: "Couldn't draw the code; the link below still works.",
  feedOff: "Couldn't turn it off. Try again.",
  upload: "Couldn't send it. Try again.",
  deleteAccount: "Couldn't delete it. Try again.",
  checkout: "Couldn't open the checkout page. Try again.",
};
