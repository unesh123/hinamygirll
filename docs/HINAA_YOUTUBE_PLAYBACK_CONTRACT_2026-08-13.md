# HINAA Verified YouTube Playback Contract — 2026-08-13

## Failure being repaired

The prior `youtube_playback_request` used `yt-dlp` to locate a video ID and `webbrowser.open()` to launch an unowned system tab. It then returned a plain success sentence without observing a YouTube page, a playable video element, a play request, or advancing playback time. The chat controller consequently rendered that optimistic response as a completed activity. The supplied screenshot is therefore evidence of a real false-completion defect, not merely a styling issue.

## Required completion state

| Stage | Required evidence | User-visible state |
|---|---|---|
| Approved | User has explicitly allowed the YouTube action. | `Running approved action` |
| Located | HINAA’s existing owned Playwright page contains one selected YouTube watch URL. | `Opening selected YouTube result` |
| Playback requested | The owned page has attempted to start the active video with an explicit control click or media `play()` request. | `Waiting for player confirmation` |
| Verified playing | The page remains on one `/watch` URL; a media element is unpaused, has a positive ready state, and its `currentTime` advances across two samples. | `Playing on YouTube` |
| Needs user interaction | YouTube opened but audio was blocked, consent/login/interstitial state appeared, no media element became ready, or time did not advance. | `Opened YouTube — press Play in the owned tab` |
| Failed | Search/navigation/player failure prevents a usable selection. | `Playback was not verified` |

A browser may block audible programmatic playback without a user gesture. HINAA must treat this as a truthful non-success state and retain a visible recovery message rather than saying a song is playing.[1] [2]

## Ownership and safety rules

The music tool reuses `browser_automation._get_page()` and must not call `webbrowser.open()`, launch `yt-dlp`, create a new context, or create another tab. It navigates the existing owned page to YouTube search, selects one first-party `/watch` result in the same tab, then tries player controls. A single explicit tool approval covers this bounded action only. HINAA cannot bypass YouTube account, age, consent, advertisement, or browser autoplay controls; when one appears, the user must interact in the owned browser tab.

## References

[1]: https://developer.chrome.com/blog/autoplay "Chrome Autoplay Policy"
[2]: https://developer.mozilla.org/en-US/docs/Web/Media/Guides/Autoplay "MDN Autoplay Guide"
[3]: https://developers.google.com/youtube/iframe_api_reference "YouTube IFrame Player API Reference"
