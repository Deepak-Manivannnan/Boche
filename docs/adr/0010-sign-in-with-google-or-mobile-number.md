# Customers sign up with Google or a mobile number; every new account has a verified number

Customers can now join and sign in two ways. **Continue with Google**: a new customer must also verify a mobile number by SMS code, then create a profile (name taken from Google and editable, age, optional delivery address); only then is the account made. **Continue with mobile number**: an SMS code to the number; a registered number signs in, a new number creates the same profile. An account made with a number signs in with the number only, until it connects a Google account from the profile, after which either way works.

## Rules

- One mobile number belongs to one account. A Google sign-up with a number that is already registered is refused before any code is sent.
- No account exists until the profile is created. The sign-up in progress (the Google identity, then the verified number) is kept in a signed, httpOnly cookie for 30 minutes.
- Profile: name (2+ characters, editable any time), age 18 or over (a prize draw), and an optional delivery address saved as the first address.
- Codes are 4 digits, sent through the same SMS service and template as the Founder's OTP, stored salted and hashed, valid 10 minutes, 5 wrong tries, used once. Sending is limited to one a minute per number while the last code is unused, five an hour per number and 20 an hour per connection, because every SMS costs money and anyone can type any number.
- Google no longer overwrites a customer's name at sign-in; the photo is still refreshed.
- Accounts made before this (Google only, no number) keep signing in with Google as before. Admins sign in on the staff page with Google only, with no mobile step.

## Consequences

- Each sign-up and each mobile sign-in sends one SMS.
- The database allows accounts without a Google id or email; the mobile number is unique.
- The old demo phone screens (a fixed demo OTP and a pretend SIM check) are no longer a way in.
