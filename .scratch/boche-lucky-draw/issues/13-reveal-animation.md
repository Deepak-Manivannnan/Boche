# 13: Reveal animation on the results screen

**What to build:** When results are published, the draw screen counts down and then reveals the Winners one at a time, from the 7th Consolation prize up to the 1st Main prize. Each lucky number appears in a matrix-style digit roll that locks digit by digit. Confetti and balloons mark the Main prizes. A signed-in Customer who won gets a personal "You won ₹X" celebration, and everyone else gets a kind "Better luck next time" message. Everything matches the existing theme.

**Blocked by:** 10

**Status:** done

- [x] A throwaway prototype of the reveal is reviewed with the developer before the final build
- [x] Reveals only Winners already fetched from the server; it never generates or implies randomness on the device
- [x] Order 7th Consolation → 1st Main; confetti and balloons for Main prizes; personalised winner and non-winner endings
- [x] A Skip button; plays once per device per Draw day; respects reduced-motion settings
- [x] Uses the existing colours, fonts, confetti and chime helpers; ends on the Winners list with a "Verify this draw" link
- [x] A JS test covers the reveal order and the personalised ending; manual check on a phone-sized screen

## Comments

- frontend/reveal.js: plan() and scrambleFrame() are pure and tested in Node; play() draws the overlay.
- Plays on the Lucky Draw screen the first time today's published result is seen on a device (localStorage flag). Skip button, reduced-motion goes straight to the ending.
- Admin 'Preview the reveal' button on a published day (useful with a Test day in the review demo).
- The prototype review was done as a rendered preview of the three states (winner ending, non-winner ending, digit roll).
