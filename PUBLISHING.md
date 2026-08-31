# Publishing this to HACS

## 1. Create the GitHub repository

Name it **`spot-the-aurora-nz`**. The repo name doesn't have to match the
integration domain, but keeping them close avoids confusion.

Make it public. HACS cannot install from private repos.

```bash
cd spot-the-aurora-nz
git init
git add .
git commit -m "Initial release"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/spot-the-aurora-nz.git
git push -u origin main
```

## 2. Add repository topics

On the repo page, click the gear beside "About" and add topics. HACS uses
these for discovery:

```
home-assistant, hacs, home-assistant-integration, aurora, space-weather, new-zealand
```

Also fill in the description field — HACS shows it in the store listing.

## 3. Cut a release

HACS installs from GitHub releases, not from the default branch.

- Releases → **Create a new release**
- Tag: `v1.0.1`
- Title: `v1.0.1`
- Describe what's in it
- Publish

The included release workflow attaches the integration folder to the
release automatically.

**Version numbers must be consistent.** The git tag and the `version` field
in `custom_components/spot_the_aurora_nz/manifest.json` must match, or HACS
will show the wrong version.

## 4. Install it yourself to test

1. HACS → ⋮ → **Custom repositories**
2. URL: `https://github.com/YOUR_USERNAME/spot-the-aurora-nz`
3. Category: **Integration**
4. Add, then find and install it

Before testing, remove your manual setup so you aren't loading the card
twice — delete the `extra_module_url` lines from `configuration.yaml` and
delete `/config/www/spot-the-aurora-nz.js`. Two copies registering the same
custom element will throw an error.

## 5. Getting into the default HACS store (optional)

Custom repositories work fine and most cards never go further. If you want
yours listed by default:

1. Your repo must pass the HACS action (the included `validate.yml` runs it)
2. Open a PR against [hacs/default](https://github.com/hacs/default)

Requirements: public repo, a description, topics set, at least one release,
a README, and a licence. This repo has all of those. Expect the PR to sit
for a while — the queue is long.

**Brand icon:** don't submit to `home-assistant/brands` - as of HA 2026.3.0
that repo no longer accepts new custom-component PRs (its own PR template
says so, pointing at the [Brands Proxy API
announcement](https://developers.home-assistant.io/blog/2026/02/24/brands-proxy-api)).
Ship the icon locally instead, at `custom_components/spot_the_aurora_nz/brand/icon.png`
(256×256, plus `icon@2x.png` at 512×512 and optionally `logo.png` /
`logo@2x.png`) - HA serves it straight from the installed integration via
the brands proxy API, and HACS's own brand-assets check looks for that
exact path before it ever falls back to checking the old brands repo. This
repo already has it.

## Maintaining it

When you change the card:

1. Edit the integration folder
2. Bump the version in the `console.info` banner
3. Commit and push
4. Cut a new release with a matching tag

Users get an update notification in HACS automatically.

## A note on the card

The Lovelace card lives inside the integration at
`custom_components/spot_the_aurora_nz/www/` and is served and registered
automatically at startup. Users never touch the Resources page. That's why
this ships as one repo rather than two.
