# Platform-native clip / highlight / short-form features and APIs (state as of 2026-11-22) and what they mean for stream2clip

Scope note: researched 2026-11-22. "Announced" = stated in an official post but not confirmed shipped; "available" = documented in a help center / API reference / changelog as live. Sources are official docs unless marked (secondary). Where only a search-result snippet was available (page not fetched), that is flagged.

## 1. YouTube: native clipping/Shorts tools, live highlights, heatmap, live chat replay, Data API changes, Shorts length and Content ID, 2025-2026 policy changes for clip channels

### Takeaway
YouTube now does inside Studio part of what stream2clip does: it suggests Shorts and clips from transcripts and auto-generates Shorts from livestreams. In 2025-2026 the Data API changed in ways that affect stream2clip directly. Uploads cost far less quota, unverified projects are no longer forced to private (so stream2clip must set `privacyStatus` explicitly), custom thumbnails now work for Shorts, and the paid-product-placement field no longer defaults to false. "Most replayed" and chat replay still have no official API; they are reachable only through yt-dlp.

### Cited Findings
**Native clipping / AI suggestions**
- YouTube Studio's "Clips and Shorts" tool cuts segments of a long-form video into a Short or a "video clip". You pick the segment from the transcript or the timeline, with optional "AI-powered suggestions" and an AI outline. Autocaptions are added and can be restyled. The final render uses a blurred crop instead of black bars. Output is a draft that goes through the normal upload flow. For a public Short, the source video is added as its "related video" automatically. YouTube states creators "won't be penalized" for reusing their own content this way. — [YouTube Help: Video clips & Shorts in YouTube Studio](https://support.google.com/youtube/answer/15824265?hl=en)
- AI suggestions/outlines are limited to selected countries (Brazil, Canada, France, Germany, India, Mexico, **South Korea**, Spain, UK, US) and languages (English, French, German, Hindi, **Korean**, Portuguese, Spanish). **Japanese is not listed.** The page covers long-form videos only and gives no channel requirements, live-stream support or rollout dates. — [YouTube Help 15824265](https://support.google.com/youtube/answer/15824265?hl=en)
- Coverage of the January 2025 launch of a "long-form content → clip Shorts" tool. — [Tubefilter, 2025-01-08](https://www.tubefilter.com/2025/01/08/youtube-long-form-content-clip-shorts-tool/amp/) (secondary; not fetched)

**Auto-generated Shorts/highlights from livestreams**
- At Made on YouTube (blog post dated **2025-09-16**), YouTube announced AI that "identifies standout moments in a livestream and turns them into Shorts" for sharing after the broadcast, shown as a "Live recap" view. The post gives no regions, languages or dates. The same post announced simultaneous horizontal+vertical ("dual format") live streaming as "Soon", with one unified chat. — [YouTube Blog: Live updates, 2025-09-16](https://blog.youtube/news-and-events/live-updates/)
- YouTube's Creator updates page lists a feature for **mobile** live streams: when the stream ends, the creator sees a Short "automatically pulled from their live stream" and can upload it. Eligibility is behind a link that was not retrieved. — [YouTube Help: Creator updates](https://support.google.com/youtube/answer/9072033) (search snippet)
- Secondary coverage says the AI highlight Shorts are saved as drafts for review and were "still rolling out". I found no official 2026 confirmation of global availability. — [Dexerto](https://www.dexerto.com/youtube/youtube-launches-ai-powered-highlight-tool-to-automatically-create-stream-clips-3252018/); [TechCrunch, 2025-09-20](https://techcrunch.com/2025/09/20/updates-to-studio-youtube-live-new-gen-ai-tools-and-everything-else-announced-at-made-on-youtube/?rand=8808) (secondary)
- Manual "Create a highlight" for streams: stream markers inserted during a live broadcast show up on the editor timeline. — [YouTube Help: Create a highlight](https://support.google.com/youtube/answer/4522163) (search snippet)

**Most replayed heatmap / chapters**
- I found no official Data API field for "Most replayed". yt-dlp exposes it as `heatmap`: "A list of dictionaries" with `start_time`, `end_time` and `value` ("normalized value … float between 0 and 1"). `chapters` comes as a list of start/end/title. — [yt-dlp extractor/common.py docstring](https://raw.githubusercontent.com/yt-dlp/yt-dlp/master/yt_dlp/extractor/common.py)
- Third-party sources say the graph appears only when a video has enough engagement. One vendor claims a 50K-view threshold, which nobody else confirms. The graph is not shown in the Shorts player. Sources disagree on whether it appears on videos with manual chapters. — [vidIQ](https://vidiq.com/es/blog/post/most-replayed-scenes-youtube-video/); [Apify scraper](https://apify.com/karamelo/youtube-most-replayed-scraper-heatmap-extractor) (secondary/commercial, unverified)
- yt-dlp's default YouTube clients are `tv_samsung,visionos,web`. `web` and `tv_samsung` are dropped when no JavaScript runtime is available. Some clients need a PO token or logged-in cookies. — [yt-dlp README](https://raw.githubusercontent.com/yt-dlp/yt-dlp/master/README.md)

**Live chat (live and replay)**
- `liveChatMessages.streamList` (gRPC server-streaming, low-latency push) costs 5 quota units per call. It uses `liveStreamingDetails.activeLiveChatId` and returns LIVE_CHAT_DISABLED/ENDED errors once chat ends, so it covers **live** chat only. — [streamList reference](https://developers.google.com/youtube/data/live/reference/rest/v3/liveChatMessages/streamList); [Streaming Live Chat guide](https://developers.google.com/youtube/data/live/streaming-live-chat) (search summary of these pages)
- The **2026-06-23** revision note removed `messageDeletedEvent`/`messageRetractedEvent` from the liveChatMessages docs "as these events are not being returned by the API". — [YouTube Data API revision history](https://developers.google.com/youtube/data/revision_history)
- Chat replay for past streams has no official API. yt-dlp treats "Live chats (if available) … as subtitles" (`--sub-langs all,-live_chat` excludes them). — [yt-dlp README](https://raw.githubusercontent.com/yt-dlp/yt-dlp/master/README.md)

**YouTube Data API changes, 2025-2026** (all from the [official revision history](https://developers.google.com/youtube/data/revision_history))
- **2024-10-30** (context): `status.containsSyntheticMedia` was added (the altered/synthetic content disclosure).
- **2025-03-26**: Shorts views count every start and replay, with no minimum watch time, effective 2025-03-31.
- **2025-12-04**: the documented cost of a video upload fell from about 1,600 to about 100 units.
- **2026-06-01**: `videos.insert` and `search.list` moved to "their own respective quota buckets". Secondary blogs say videos.insert = 100 calls/day by default; I did not verify that figure officially. — [SociaVault](https://sociavault.com/blog/youtube-data-api-quota-2026) (secondary)
- **2026-06-03**: `videos.batchGetStats` was added (1 unit, own bucket, default 10,000 units/day).
- **2026-07-07**: a `brandPartner` part (`channelId`/`channelHandle`) was added to videos.insert/update/list.
- **2026-08-27**: public views count "the moment a video begins to play" across long-form, Live and Shorts. Engaged views still drive monetization.
- **2026-09-11**: new thumbnail keys `fhd`/`qhd`/`uhd`, available for some videos only.
- **2026-09-14**: max file size for `thumbnails.set` and `playlistImages.insert` rose from 2 MB to **50 MB**.
- **2026-11-02**: videos uploaded via `videos.insert` from unverified projects "are no longer restricted to private viewing mode". This reverses the 2020-07-28 policy. **If `privacyStatus` is not specified, uploads default to `public`**, unless the creator's account default says private.
- **2026-11-03**: `thumbnails.set` "now supports uploading custom thumbnails for YouTube Shorts after video processing is complete". The new field `shortsAspectRatio` was added to the thumbnails resource.
- **2026-11-16**: `paidProductPlacementDetails.hasPaidProductPlacement` no longer defaults to `false` and must be set explicitly. Co-views now count in public views. A `posts` resource is in pilot for select partners, with broader access planned for 2027.
- I found no revision-history entry adding API support for Collaborations (multi-channel collab videos) or for chapters/Shorts detection.

**Shorts length and Content ID**
- Shorts can run up to 3 minutes for uploads on or after **2024-10-15**; Official Artist Channels followed from **2025-12-08**. A video must be square or vertical to be classified as a Short. Uploads before 2024-10-15 stay long-form. — [YouTube Help: Understand three-minute Shorts](https://support.google.com/youtube/answer/15424877?hl=en)
- A Short **over one minute with an active Content ID claim of any type (including manual) is blocked globally**: it can't be played, recommended or monetized, though it carries no strike. Shorts under one minute are unaffected. Most Shorts Audio Library songs can be used for up to 90 s, some only 60 s or 30 s. — [YouTube Help 15424877](https://support.google.com/youtube/answer/15424877?hl=en); [Learn about Content ID claims](https://support.google.com/youtube/answer/6013276?hl=en)

**Policy changes affecting clip/kirinuki channels**
- On **2025-07-15**, YPP renamed "repetitious content" to "inauthentic content" (repetitive or mass-produced content). YouTube says there is "no change to our reused content policy", which covers clips and compilations and asks whether there is a "meaningful difference" from the original. Violations can remove monetization from the whole channel. — [YouTube Help: YPP policies](https://support.google.com/youtube/answer/1311392?hl=en); [Search Engine Journal](https://www.searchenginejournal.com/youtube-clarifies-monetization-update-targeting-spam-not-reaction-channels/550755/) (secondary)

### Inferences
- **Must fix/verify:** since 2026-11-02, a stream2clip upload that omits `privacyStatus` may go **public**. A repo check (2026-11-22) shows `src/stream2clip/upload.py` line 75 always sends `status.privacyStatus`, and tests assert `"private"`, so current code is safe. The new risk is that any future upload path that leaves the field out would now publish publicly. `status.containsSyntheticMedia` is already supported (upload.py lines 50 and 84). **Not yet handled:** `paidProductPlacementDetails.hasPaidProductPlacement` no longer defaults to false (2026-11-16), and no reference to it exists in the repo. Sending `false` explicitly, or exposing it as an option, is advisable.
- **New capability:** custom thumbnails for Shorts via `thumbnails.set` (2026-11-03), with a 50 MB limit and a new `shortsAspectRatio` field. stream2clip's thumbnail generator can now apply to 9:16 uploads. The upload has to wait until processing completes, so a poll/retry step is needed.
- With uploads at about 100 units, quota stops being the bottleneck. The new per-method bucket (reportedly about 100 inserts/day) is now the cap, so batch scheduling should be planned around it.
- **Differentiation versus YouTube's own tools:** they work only on the creator's *own* videos, AI suggestions exclude Japanese, and they don't use chat bursts, superchats or the heatmap of someone else's stream. Kirinuki channels clip *other people's* streams, which YouTube's tools don't cover. stream2clip's multi-signal detection and Japanese/Korean subtitle handling remain distinctive. Still, for streamers clipping their own streams, "Live recap" auto-Shorts is direct competition.
- **Content ID rule for Shorts:** a VTuber karaoke (utawaku) or BGM-heavy segment cut to 61-180 s that draws any claim is globally blocked. stream2clip should flag music-heavy segments and recommend ≤60 s for those, or a horizontal long-form export instead.
- **Reused-content risk:** auto-generated clips with minimal editing are exactly what the reused/inauthentic policy targets. Features that add "meaningful difference" (translated subtitles, context titles, commentary) also count as monetization safety.
- The heatmap and chat replay depend on yt-dlp internals (PO tokens, JS runtime, client changes). That is a fragility to monitor, and stream2clip should degrade gracefully when the heatmap is missing (low-view streams, Shorts).

### Gaps
- Official eligibility, regions and languages for the AI "Live recap" auto-Shorts were not found. I could not confirm whether Japanese/Korean streams are supported or whether it ships on desktop streams.
- Official per-day `videos.insert` bucket size after 2026-06-01; only secondary sources give about 100/day.
- Whether the Data API can set the Shorts "related video" link, or Collaborations (co-creator) metadata: not found.
- Whether dual-format (vertical+horizontal) YouTube live has fully launched: not confirmed after the 2025-09 "Soon".
- Official threshold for when "Most replayed" appears: not documented.

## 2. Twitch (and Kick): Clips API, vertical clips, Auto Clips, clip editor, markers, API limits

### Takeaway
In 2025-2026 Twitch made clips much more API-accessible. Get Clips Download went GA on 2025-10-30 and Create Clip From VOD went GA on 2026-02-05. Create Clip gained title, duration, 2K and **vertical output from Dual Format streams**. Twitch also announced native Auto Clips (chat, voice and on-screen signals), auto captions and top-clip lists, so its native tools now overlap stream2clip's core loop. Kick has a public API, but I found no official clips endpoint.

### Cited Findings
- **2025-09-19**: Get Clips Download entered open beta; it went GA on **2025-10-30**. It "provides URLs to download the video file(s) for the specified clips". — [Twitch Docs changelog](https://dev.twitch.tv/docs/change-log/)
- **2025-12-19**: Create Clip From VOD entered open beta. Create Clip gained "2K video, vertical video from dual-format streams, optional `title` and `duration` parameters, and an updated edit URL". **2026-02-05**: Create Clip From VOD became GA. — [Twitch Docs changelog](https://dev.twitch.tv/docs/change-log/)
- From the forum announcement (2025-12-20): Create Clip From VOD takes a video ID plus an offset and can also clip earlier in a current live stream if VODs are enabled. The edit URL offers title editing, "portrait versions", export to third-party platforms, and downloads of the landscape and portrait versions. `has_delay` was removed. Required scopes are `channel:manage:clips` (broadcaster) or `editor:manage:clips` (editor or higher). The authenticated user must be the broadcaster or an editor; an app's owner doesn't matter. — [Twitch Dev Forums](https://discuss.dev.twitch.com/t/introducing-clip-api-improvements-and-clip-from-vod-in-open-beta/64492)
- Known beta issues: VOD clips ended about 2-9 s later than `vod_offset` + duration implied (reported 2025-12-24). Twitch confirmed the cause on 2026-01-08 and said it would be fixed before GA. Users also reported that edit URLs no longer opened the full editor with orientation options (2026-01-12/13). — [Twitch Dev Forums](https://discuss.dev.twitch.com/t/introducing-clip-api-improvements-and-clip-from-vod-in-open-beta/64492)
- **2026-11-10** doc fixes: Get Clips no longer promises results in input-ID order and drops the unsupported `before` parameter. Get Stream Markers drops `before` and says markers are ordered by position in the video. Get Videos adds `past_premiere`/`premiere_upload` types. — [Twitch Docs changelog](https://dev.twitch.tv/docs/change-log/)
- Other 2026 API context: app access token support went GA on 2026-05-29, and `channel.chat.message` gained a `gif` fragment type on 2026-07-16. — [Twitch Docs changelog](https://dev.twitch.tv/docs/change-log/)
- **TwitchCon Rotterdam (Twitch blog, 2026-05-30)**:
  - **Auto Clips** is *coming*: beta "in the coming months", with a waitlist open. It makes captioned clips from chat activity, vocal inflection and on-screen events, and saying "Twitch Clip That" also triggers a clip. Twitch says 85% of Auto Clips users have a clip after a stream, versus 50% overall.
  - **Clip captions** (auto-generated and editable) began rolling out the week after the event.
  - **Top-clips lists** in stream summaries start June 2026.
  - **Dual Format** (simultaneous horizontal+vertical) is in beta, with rollout "next month" (June 2026).
  - Auto-cropping and auto-trimming are "being explored" and not announced.
  - — [Twitch Blog: Everything we announced at TwitchCon Rotterdam 2026](https://blog.twitch.com/en/2026/05/30/everything-we-announced-at-twitchcon-rotterdam-2026/)
- Twitch's own post (on X) said Dual Format would come "to everyone next month". Mashable-type coverage instead reported a summer test with a few channels; the sources conflict on rollout breadth. — [Twitch on X](https://x.com/Twitch/status/2060648789044551718?lang=en); [Tubefilter, 2026-06-01](https://www.tubefilter.com/2026/06/01/twitch-twitchcon-europe-rotterdamn-vertical-horizontal-dual-format-stream/) (secondary)
- One secondary source says Auto Clips is alpha and English-only, and that Twitch has shipped "a vertical version of every clip for Dual Format streams". Unverified against Twitch. — [cut.pro blog](https://cut.pro/en/blog/twitch-wants-your-clips-2026); [streamer.guide](https://streamer.guide/blog/twitchcon-rotterdam-2026-new-features-1440p-clips-guilds) (secondary)
- Background: Twitch's vertical clip editor for TikTok/Reels-style sharing dates from May 2023. — [TechCrunch, 2023-05-11](https://techcrunch.com/2023/05/11/twitch-clip-editor-edit-vertical-video-tiktok-reels)
- **Kick**: Kick has launched a public API and welcomes third-party developers. I found no official clips endpoint; only third-party scrapers offer Kick clips data. — [KickDevDocs README](https://raw.githubusercontent.com/KickEngineering/KickDevDocs/main/README.md) (search summary); [Anysite Kick clips (third-party)](https://docs.anysite.io/api-reference/kick/kickchannelsclips)

### Inferences
- **Integration opportunity:** for streamers who authorize stream2clip as broadcaster or editor, stream2clip could call Create Clip From VOD at its detected highlight offsets, then Get Clips Download. That yields Twitch-native clips (vertical too, when the stream was Dual Format), which count toward the streamer's Clips page. Offsets were off by about 2-9 s in beta; even with the fix, stream2clip should pad or re-verify boundaries.
- For Dual Format streams, Twitch's native vertical variant is a better 9:16 source than cropping the horizontal VOD. It is worth detecting and preferring when it can be downloaded.
- Third-party clippers without editor rights can't use these endpoints. They still rely on VOD download plus chat replay (yt-dlp / GQL), which is unofficial.
- **Competition:** Auto Clips uses the same signals as stream2clip's detector (chat, voice energy, on-screen events). Once it is widely available, Twitch streamers get basic auto-clips for free. stream2clip's differentiation will be cross-platform support, kirinuki editing (subtitles, titles, thumbnails, colour-coded speakers), horizontal compilations and YouTube publishing, none of which Twitch does.
- Twitch stream markers (Get Stream Markers, ordered by video position) remain a cheap, high-precision signal that stream2clip already uses.

### Gaps
- Twitch Helix rate-limit numbers for the clip endpoints were not retrieved in this session.
- Whether Get Clips Download needs broadcaster/editor authorization or can fetch any public clip was not confirmed.
- I did not confirm whether the VOD-offset bug was actually fixed at GA (2026-02-05).
- Auto Clips' current status as of November 2026 (still beta/waitlist? languages?) was not found in an official source.
- Whether Kick has any clip-creation endpoint was not confirmed.

## 3. CHZZK (Naver) and SOOP (AfreecaTV): native clip/short-form features, official Open APIs, policies for third-party clips

### Takeaway
Both Korean platforms have native clips and vertical short-form: CHZZK Clip, which feeds Naver "Clip", and SOOP's User Clip and Catch. Naver runs an in-house AI auto-clipper, "Spotter", but only for official sports/esports broadcasts. CHZZK's official Open API covers user, channel, category, live and chat (real-time Session events), with **no clip or VOD endpoints**. For SOOP I found no public official Open API documentation. SOOP's **VOD replay retention cut, effective 2026-06-01**, matters for stream2clip because source VODs can now expire.

### Cited Findings
**CHZZK / Naver**
- CHZZK added a clip feature at its official launch. — [ETNews, 2024-05-09](https://www.etnews.com/20240509000113) (search snippet)
- The August 2024 update added "clip collection" and streamer "clip upload" (beta). — [ETNews, 2024-08-04](https://www.etnews.com/20240804000043) (search snippet)
- CHZZK short-form was slated to appear in Naver app Clip (Oct 2024 update notice). — [FMKorea repost of CHZZK update notice](https://www.fmkorea.com/7637147273) (secondary)
- Naver is closing Naver TV on **2026-09-30** and unifying short- and long-form under "Clip", with live streaming concentrated on CHZZK. Creator profile migration to Clip started on 2026-09-10. — [CEO Score Daily, 2026-07-31](https://m.ceoscoredaily.com/page/view/2026073115184183238) (search snippet)
- **Spotter** is Naver's AI clip-generation system for CHZZK live broadcasts. It was applied to every match of the 2026 World Cup: 3,452 clips, about 127.5M views, with clips typically ready about 3.7 minutes after the moment. For EWC 2026 it generated 3,038 clips over 31 days, and clip views on EWC's official channel rose 2.9x year over year. Clips are distributed across CHZZK, the Naver app home/Clip tab, integrated search and other surfaces. The article does not say Spotter is available to individual streamers. Naver also plans an integrated "channel search" that shows a creator's live, clips and VOD together. — [ETNews, 2026-09-10](https://www.etnews.com/20260910000307)
- The CHZZK Open API (domain `openapi.chzzk.naver.com`) lists five categories: User, Channel, Category, Live and Chat. No Clip or VOD category exists. — [CHZZK API docs](https://chzzk.gitbook.io/chzzk); [CHZZK API tips](https://chzzk.gitbook.io/chzzk/chzzk-api/tips)
- **CHZZK Session API** (real-time events):
  - Client sessions need app registration and allow up to 10 connections. User sessions allow "up to 3 connections per user".
  - Events are CHAT, DONATION (chat or video) and SUBSCRIPTION (tier 1/2), each needing its own scope, with at most 30 event subscriptions per session.
  - Supported clients are Socket.IO-client 1.0.0-2.0.3.
  - Disconnected sessions remain listable for 90 days; a community record says this note was added on 2026-07-26.
  - The docs mention no replay/past-broadcast chat. — [CHZZK Session API](https://chzzk.gitbook.io/chzzk/chzzk-api/session); [community test gist](https://gist.github.com/fi-xz/69ce1f35ca1b2318a2b410c0d5757e0f)
- A community project notes that the official API can't auto-detect broadcast start and end. — [chzzk-chat-collector (GitHub)](https://github.com/YuJY9897/chzzk-chat-collector) (secondary)
- CHZZK's studio content guideline revision (effective about 2025-10-15) targeted inappropriate broadcast content such as "excel broadcasts". It is not a clip or derivative-work policy. — [Newsis, 2025-09-16](https://mobile.newsis.com/view/NISX20250916_0003331513) (search snippet)

**SOOP**
- **User Clip** makes VOD clips "ranging from 20 seconds to 5 minutes", with a preview of up to 10 minutes back. Clips can't be made in some categories, such as "Music (streaming)" and some professional sports. — [SOOP Help: What is a User Clip](https://sooplive.helpshift.com/hc/en/3-soop/faq/268-what-is-a-user-clip/)
- SOOP's clip guide says general users (not only streamers) can now create clips of up to 5 minutes, and only the video owner can edit or delete them. — [SOOP Help: Clip creation guide for all users](https://sooplive.helpshift.com/hc/en/3-soop/faq/52-clip-creation-guide-for-all-users) (search snippet; not fetched)
- **Catch** is "a short video under 3 minutes, displayed in a 9:16 vertical player". It is created from LIVE or VOD via the Clip/Catch button, in 9:16, 1:1, 4:3 or 16:9. Uploaded VODs of 3 minutes or less with height ≥ width are auto-converted to Catch. — [SOOP Help: What is Catch](https://sooplive.helpshift.com/hc/en/3-soop/faq/269-what-is-catch/)
- A search snippet describes "Catch Story" as AI that compresses long live broadcasts into multiple short stories. The fetched help page does not mention it, so this is unverified. — [SOOP Help 269 (snippet)](https://sooplive.helpshift.com/hc/en/3-soop/faq/269-what-is-catch/)
- **VOD replay retention change, effective 2026-06-01**, applied to existing replays too:
  - Basic streamers: 90 days by default, 1 year with 50+ unique views (previously permanent with 50+ views or 10 balloons).
  - Best streamers: 2 years by default, permanent above 1,000 unique views (previously permanent).
  - Partners: unchanged (permanent).
  - Clips, Catch and uploaded VODs are unaffected. SOOP advises streamers to download replays they want to keep. — [SOOP Help: VOD replay retention policy](https://sooplive.helpshift.com/hc/en/3-soop/faq/284-notice-changes-to-vod-replay-retention-policy/)
- SOOP AI: the SOOPi assistant was updated on 2026-06-19 and opened to all users; it is built on SOOP's own video model trained on streamer broadcasts. The 2026 strategy (announced 2025-12) emphasized AI, including the generative video tool SAVYG. I found no official SOOP AI auto-highlight/clip product announcement. — [Betanews, 2026-06-19](https://www.betanews.net/article/view/beta202606190032); [Nate/News, 2025-12-27](https://m.news.nate.com/view/20251227n08818) (secondary)
- SOOP officially supports the Nightbot chatbot, a third-party chat integration. — [SOOP Help: Nightbot](https://sooplive.helpshift.com/hc/en/3-soop/faq/288-how-to-enable-and-configure-nightbot-for-soop-streams/?p=ios)
- Third-party wrappers read SOOP public web endpoints (e.g. `chapi.sooplive.co.kr/api/{bj}/station`). These are not an official Open API. — [oanor SOOP API](https://www.oanor.com/api/soop-api) (third-party)

**Third-party clip policy (derivative works)**
- I found no platform-level CHZZK or SOOP policy on third-party kirinuki/derivative clips. Rules are set by streamers or agencies, for example individual VTuber clipping guidelines that forbid commercial use. — [Ruliweb: 이로아 2차 창작 가이드라인](https://bbs.ruliweb.com/etcs/board/700392/read/18986) (secondary)

### Inferences
- **No official clip/VOD API on either Korean platform** means stream2clip must keep relying on yt-dlp or its own extractors for CHZZK/SOOP VODs and chat replay. It should treat these as fragile and version-pin and monitor them.
- CHZZK's official Session API delivers CHAT/DONATION events **live only**. That fits stream2clip's live mode: a CHZZK live chat-burst detector paired with the OBS replay buffer, via an official, ToS-safe path. It needs the streamer's OAuth (user session) or a registered app (client session).
- **SOOP retention:** for Basic streamers with little traffic, a VOD now disappears after 90 days. stream2clip should prompt users to process or download SOOP VODs early, and should store the chat replay alongside the cached VOD. A "VOD expiring" warning based on tier and view count would be a cheap win.
- SOOP blocks User Clips in music categories, and YouTube blocks >60 s claimed Shorts. Both point to music segments as a high-risk zone that the detector should label.
- Naver's Spotter shows the auto-clip approach working at scale for sports. If Naver opens it to streamers, it would compete directly on CHZZK. stream2clip can differentiate on kirinuki-style editing and YouTube distribution, since Naver's Clips stay inside Naver.

### Gaps
- No official SOOP developer/Open API documentation was found (openapi/developers.sooplive.co.kr did not surface). I could not determine whether SOOP offers official chat, VOD or clip APIs to third parties.
- CHZZK clip permissions (can streamers disable viewer clips? can clips be downloaded or uploaded via API?) were not found.
- I found no platform-level CHZZK or SOOP policy on monetized third-party clip channels (2차 창작) in this session.
- Whether CHZZK clips are now vertical-first after the Naver Clip unification was not confirmed.

## 4. TikTok, Instagram Reels, X: posting APIs, audit steps for a desktop app, length and caption limits

### Takeaway
All three can be automated, but each has hurdles for an open-source desktop app:
- **TikTok:** audit needed to post publicly; strict UX rules for the post screen.
- **Instagram:** professional account required; video must sit at a public URL or go through resumable upload under Facebook Login for Business.
- **X:** pay-per-use credits.

stream2clip's current YouTube-only scope avoids all of this. If it adds platforms, TikTok's "unaudited = private only, up to 5 users/24h" is the binding constraint.

### Cited Findings
**TikTok Content Posting API (Direct Post)**
- Scope is `video.publish`, used with a user access token. Apps must query `creator_info` first and render its privacy options. `privacy_level` must match one of the returned options (PUBLIC_TO_EVERYONE, MUTUAL_FOLLOW_FRIENDS, FOLLOWER_OF_CREATOR, SELF_ONLY).
- `title` (caption) max is 2,200 UTF-16 runes, with #hashtags/@mentions parsed from the text.
- Rate limit is 6 requests/min per user token. Exceeding the daily post cap returns `spam_risk_too_many_posts`.
- FILE_UPLOAD (chunked; mp4/quicktime/webm) needs no hosting, and its `upload_url` is valid for 1 hour. PULL_FROM_URL requires verified domain ownership.
- Flags: `brand_content_toggle`, `brand_organic_toggle`, and `is_aigc` (adds the "Creator labeled as AI-generated" label).
- — [TikTok Direct Post reference](https://developers.tiktok.com/doc/content-posting-api-reference-direct-post)
- Unaudited clients: content is restricted to private viewing, and posting to a public account fails with `unaudited_client_can_only_post_to_private_accounts`. An audit is required to lift this. — [TikTok Direct Post reference](https://developers.tiktok.com/doc/content-posting-api-reference-direct-post)
- Content sharing guidelines:
  - Limits: "Unaudited API Clients can allow up to 5 users to post in a 24 hour window", with accounts private at posting time. The posting cap is "typically around 15 posts per day/creator account", shared across all Direct Post clients. A per-client active-creator cap is set from the audit application's usage estimates.
  - UX rules: show the creator's nickname; check duration against `max_video_post_duration_sec`; privacy dropdown with "no default value"; comment/duet/stitch toggles unchecked by default; a Music Usage Confirmation declaration; a commercial-content toggle; a preview; posting only with express consent.
  - Apps "should not superimpose brand names, logos, watermarks, promotional branding, links, or promotional text", and preset titles/hashtags must be editable.
  - — [TikTok Content Sharing Guidelines](https://developers.tiktok.com/doc/content-sharing-guidelines)
- App review for the `video.publish` scope is separate from the audit and "may take several days to two weeks". — [AdaptlyPost](https://adaptlypost.com/blog/why-does-my-app-need-approval-post-tiktok); [Socialync](https://www.socialync.io/blog/tiktok-content-posting-api-guide-2026) (secondary)

**Instagram Graph API (Reels)**
- Requires an Instagram professional account. With Instagram Login the permissions are `instagram_business_basic` + `instagram_business_content_publish`. With Facebook Login they are `instagram_basic`, `instagram_content_publish` and `pages_read_engagement`. Pages needing Page Publishing Authorization can't be published to until PPA is done. — [Meta: Content Publishing](https://developers.facebook.com/docs/instagram-platform/content-publishing/)
- Rate limit: "100 API-published posts within a 24-hour moving period". The carousel section of the same page says 50, a conflict within the docs. Usage is queried with `GET /<IG_ID>/content_publishing_limit`. — [Meta: Content Publishing](https://developers.facebook.com/docs/instagram-platform/content-publishing/)
- Media must be hosted on a publicly accessible URL when publishing. Resumable upload via `rupload.facebook.com` (local file) is "only available to apps using Facebook Login for Business". Other features: trial reels (`trial_params`, MANUAL/SS_PERFORMANCE graduation), `is_ai_generated=true` disclosure, and a published reel reporting `media_type=VIDEO` with `media_product_type` = REELS. — [Meta: Content Publishing](https://developers.facebook.com/docs/instagram-platform/content-publishing/)
- Reels specs and options:
  - File: MOV/MP4 with moov atom at the front; H.264/HEVC; AAC ≤48 kHz; 23-60 fps; max 1,920 columns; 9:16 recommended; ≤25 Mbps; **3 s-15 min**; **≤300 MB**.
  - Caption: **2,200 characters, 30 hashtags, 20 @mentions**.
  - Options: `cover_url` (JPEG ≤8 MB) or `thumb_offset`, up to 3 `collaborators`, and `share_to_feed`.
  - — [Meta: IG User Media reference](https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/reference/ig-user/media)
- Reels-tab eligibility of 5-90 s at 9:16 is a third-party claim that I did not find in Meta's docs. — [Postproxy](https://postproxy.dev/blog/instagram-reels-api-publishing-guide/) (secondary)

**X API**
- Pay-per-use credits, with no subscription required:
  - Post create: $0.015. Post create with a URL: **$0.200**.
  - Post read: $0.005 per resource. Media metadata: $0.005 per request.
  - Reads are capped at 3M post reads per month on pay-per-use.
  - No separate media-upload price is listed. — [X Docs: Pricing](https://docs.x.com/x-api/getting-started/pricing.md)
- Another official page reportedly cites a 2M monthly read cap, which conflicts with the 3M on the pricing page. — [X Docs: Post cap](https://docs.x.com/x-api/fundamentals/post-cap.md) (search summary)
- Video upload is chunked (init/append/finalize), with init up to 16 GB. Max post video length is 20 minutes for default accounts and 125 minutes for Premium. — [X Docs: Media best practices](https://docs.x.com/x-api/media/quickstart/best-practices) (search summary)
- Third-party figure: POST /2/tweets limited to 100 per user per 15 min and 10,000 per app per 24 h. — [Socialync](https://www.socialync.io/blog/x-api-pricing-and-posting-2026) (secondary)

### Inferences
- **TikTok:** an open-source desktop app has a structural problem. Each fork or user would need their own developer app and audit, or the project would need one audited client whose secret ships in a public repo. The TikTok "Upload" (draft-to-inbox) path, where the user finishes the post in the TikTok app, is likely the realistic option, but I did not verify its rules. The no-default-privacy and editable-hashtag UX rules would need a dedicated post dialog. The rule against superimposed watermarks/branding may conflict with stream2clip adding its own logo; a creator's own channel branding is ambiguous.
- **Instagram:** the public-URL requirement means stream2clip would need a temporary public host, or Facebook Login for Business with resumable upload. It requires a professional account and Meta app review (Advanced Access). Caption limits (2,200 characters / 30 hashtags) are compatible with stream2clip's hashtag generator, but the generator should enforce the 30-hashtag cap.
- **X:** cheap per post, but $0.20 if the post contains a URL (e.g. a link back to the source stream). Video limits are generous. It is practical for an optional "post with your own API key" feature.
- **Common denominator:** captions ≤2,200 on TikTok and IG, vertical 9:16 H.264/AAC MP4, and AI-content flags on every platform (TikTok `is_aigc`, IG `is_ai_generated`, YouTube `containsSyntheticMedia`). A single per-clip metadata model with an "AI-generated/altered" boolean, a "paid promotion" boolean and a hashtag list capped per platform would make future integrations straightforward.

### Gaps
- TikTok's `max_video_post_duration_sec` values and the rules for the Upload (draft/inbox) flow for unaudited apps were not retrieved.
- Whether TikTok OAuth supports desktop/loopback redirect URIs was not checked.
- Meta app-review steps for a desktop/OSS app and the current Reels-tab duration eligibility were not found officially.
- X media upload pricing (if any) and official per-user post rate limits were not verified.

## 5. Bilibili / Niconico (briefly) and agency-level rules relevant to VTuber clips

### Takeaway
I found no reliable 2025-2026 platform-level information on Bilibili or Niconico clip features or APIs in this session. For VTuber kirinuki, agency rules are tightening: Nijisanji's guidelines, revised 2025-05-23, now explicitly require registering a clip channel before posting clips.

### Cited Findings
- On **2025-05-23** ANYCOLOR (Nijisanji) revised its secondary-creation guidelines. Making and posting kirinuki now requires prior registration through the "clip channel registration form" (the form has existed since May 2023), and ANYCOLOR may request removal of violating clips. — [KAI-YOU](https://kai-you.net/article/92488)
- Individual talents can impose stricter rules, for example a January 2025 report of a VTuber banning clips without permission. — [Dengeki Online, 2025-05](https://dengekionline.com/article/202505/42795) (search snippet)
- Korean VTuber/streamer clipping guidelines exist per talent (e.g. no commercial use). — [Ruliweb: 이로아 가이드라인](https://bbs.ruliweb.com/etcs/board/700392/read/18986) (secondary)

### Inferences
- Platform tools don't enforce agency rules, so stream2clip could add value with a per-streamer "clip policy profile": allowed or not, monetization allowed, required credit or link format, and registration needed. It would auto-insert the required credit or source-link text into descriptions and warn before upload.

### Gaps
- Bilibili 切片 (clip) authorization programs, upload APIs and VTuber clip policies were not researched successfully; searches returned nothing relevant.
- Niconico 2026 status (post-2024 cyberattack recovery, clip/kirinuki guidelines, APIs) was not found.

## 6. Analytics APIs a tool could use to learn which clips performed (YouTube Analytics / Reporting, plus related)

### Takeaway
The YouTube Analytics API already supports separating Shorts, live and VOD (`creatorContentType`). It added `engagedViews` (2025) and thumbnail impressions/CTR reach reports (2026-01-15). Data lags 48-72 h. Together with `videos.batchGetStats` (1 unit), this is enough for stream2clip to build a feedback loop that tunes highlight-detection weights and title/thumbnail choices from real clip performance.

### Cited Findings (all from [YouTube Analytics & Reporting API revision history](https://developers.google.com/youtube/analytics/revision_history) unless noted)
- The `creatorContentType` dimension (LIVE_STREAM, SHORTS, STORY, VIDEO_ON_DEMAND) has existed since 2022-12-15. Retention-related metrics (`startedWatching`, `stoppedWatching`, `totalSegmentImpressions`) were added 2024-05-06.
- **2025-03-26 / 2025-04-24 / 2025-06-24**: the Shorts view-counting change. `views` now counts starts and replays, and the new `engagedViews` metric keeps the old methodology. Targeted Queries were updated by 2025-04-30 and Bulk Reports by 2025-06-30, with new report versions and an `engaged_views` column.
- **2026-01-15**: reach reports for channels and content owners, with the new metrics `video_thumbnail_impressions` and `video_thumbnail_impressions_ctr`.
- **2026-08-27**: public views count from first frame; `engagedViews` is unchanged and still drives monetization.
- **2026-09-09**: data freshness is a 48-72 hour delay. Monetary metrics are YPP-only; non-monetized channels get HTTP 403.
- **2026-11-06**: new playback locations: `SHORTS_FEED` and `IMMERSIVE_LIVE_FEED` (Analytics), and Reporting values 11 (vertical live feed) and 12.
- **2026-11-16**: co-views are included in views and watch time.
- In the Data API, `videos.batchGetStats` (2026-06-03) costs 1 unit in its own 10,000-units/day bucket and returns per-video statistics in bulk. — [YouTube Data API revision history](https://developers.google.com/youtube/data/revision_history)
- Twitch: TwitchCon 2026 announced top-performing clip lists in post-stream summaries starting June 2026. I found no new clip-analytics API endpoint. — [Twitch Blog, 2026-05-30](https://blog.twitch.com/en/2026/05/30/everything-we-announced-at-twitchcon-rotterdam-2026/)
- Instagram exposes `content_publishing_limit` for quota. I found no evidence about Reels-insights API changes in this session. — [Meta: Content Publishing](https://developers.facebook.com/docs/instagram-platform/content-publishing/)

### Inferences
- **Feedback loop design:** for each uploaded clip, store detection features (chat-burst z-score, superchat sum, loudness, heatmap value, marker presence) and creative choices (title template, thumbnail variant, length, 9:16 vs 16:9). After 72 h or more, pull Analytics with the `yt-analytics.readonly` scope:
  - `engagedViews` and `averageViewPercentage` per video;
  - `creatorContentType` to split Shorts from horizontal;
  - `insightPlaybackLocationType=SHORTS_FEED`;
  - reach reports for thumbnail CTR.

  Then fit detector weights and title/thumbnail preferences per channel. Use `videos.batchGetStats` for cheap daily public stats.
- Because views now count from the first frame (2026-08-27), `engagedViews` and retention are the better success metrics than `views` for Shorts.
- Thumbnail CTR from reach reports, combined with the new Shorts custom thumbnails (2026-11-03), makes it possible to A/B thumbnails on Shorts. This is a differentiating feature for a clip tool.
- This only works for channels the user owns and authorizes (OAuth). Kirinuki channels own their uploads, so this fits stream2clip's users.

### Gaps
- Exact current metric names for Shorts-specific retention (e.g. `audienceWatchRatio` via `elapsedVideoTimeRatio`) were not confirmed in the fetched revision entries.
- Whether YouTube's in-Studio "Test & Compare" thumbnail A/B testing is exposed via API was not researched.
- TikTok Display/Research API and Instagram Insights metrics for Reels were not researched.
