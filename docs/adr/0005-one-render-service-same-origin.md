# One Render web service serves both the frontend and the API

The FastAPI backend serves the prototype's static files and the `/api` routes from one Render web service on one domain. With separate frontend and API domains, the Google sign-in session cookie becomes third-party and is blocked by Safari and incognito Chrome; one origin removes that problem and any need for CORS. Render's free service sleeps after 15 minutes idle, so Draw day steps are applied whenever they are due on any incoming request, with external scheduled pings at 8:00, 8:15 and 8:30 PM as a backup.

## Considered Options

- **Static site plus a separate API service with a rewrite rule**: workable, but two deployments and the same cookie pitfalls if the rewrite is misconfigured.

## Consequences

- Render's free plan has no pre-deploy step, so database migrations run in the start command before the server starts. Migrations must therefore stay safe to run on every start.
- The prototype's service worker must never cache `/api` responses, because they share the origin with the cached app shell.
