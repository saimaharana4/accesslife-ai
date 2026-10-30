# Taste Duel assets

Recorded 24 October 2026. This manifest covers the original visual system,
not external Qloo data or a licence to third-party promotional imagery.

Live application extension (26 October 2026): the same project-owned compositions are
used as explicitly labelled original title cards for live Qloo entities. They
are not official posters, artist photographs or provider artwork. Titles remain
outside the image. Missing/unapproved provider image metadata does not cause a
remote fetch; only the four exact local asset IDs are allowed. Original fallback
art is sufficient, so no optional external image provider is enabled.

| Asset                                                                    | Source / rights                                                         | Use                                                        |
| ------------------------------------------------------------------------ | ----------------------------------------------------------------------- | ---------------------------------------------------------- |
| `apps/web/public/art/{afterlight,blue-hour,velvet-static,slow-burn}.svg` | Original geometric SVG created for this project; repository MIT licence | Fictional film/artist choice cards and landing composition |
| CSS wordmark, ticket, seam and fallback title cards                      | Original project composition; repository MIT licence                    | Prototype UI, no external logo or copied poster            |
| `BarlowCondensed-Bold.ttf`                                               | Copyright 2017 The Barlow Project Authors; SIL Open Font License 1.1    | Locally hosted display type, weight 700                    |
| `Manrope-variable.ttf`                                                   | Copyright 2018 The Manrope Project Authors; SIL Open Font License 1.1   | Locally hosted reading type, weights 400/600               |

Fonts were retrieved without modification from the official
[Google Fonts repository at `e7db6ca603fd4862010383ff17ffd6cc4ffac1c0`](https://github.com/google/fonts/tree/e7db6ca603fd4862010383ff17ffd6cc4ffac1c0/ofl).
Full notices: [Barlow Condensed OFL](../../apps/web/public/fonts/BarlowCondensed-OFL.txt)
and [Manrope OFL](../../apps/web/public/fonts/Manrope-OFL.txt). Exact immutable source
URLs, SHA-256 hashes and file sizes are in the
[font provenance manifest](../../apps/web/public/fonts/provenance.json).

The browser requests only locally served files; there is no runtime Google Fonts
request. The repository MIT licence does not replace the OFL notices. Retain the
notices with distributed font files.

All entity names, dates, outcomes and scores in the development fixture are invented
design specimens. No Qloo response, external film poster, artist photo or provider
image URL was imported. Original fallback cards are sufficient; TMDB/Commons and
other optional providers are not enabled. Artwork presence does not prove rights
to unrelated external assets.

The [public artwork notice](../../apps/web/public/assets-LICENSE.md) describes each
original illustration. Local screenshots and axe outputs are ignored artifacts,
not additional licensed source data.
