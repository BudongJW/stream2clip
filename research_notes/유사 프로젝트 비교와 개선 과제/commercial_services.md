# Commercial AI clipping / short-form repurposing services (as of Nov 2026) vs stream2clip

Scope note: research done 2026-11-22. Most "comparison" articles in this space are written by vendors who rank themselves first (Reap, ClipMe, StreamLadder, Eklipse, KIRARI, CapCut, Cut.pro, etc.); these are flagged. Prices change often and sources conflict; vendor pricing pages fetched directly are preferred where available. "Claim" = vendor marketing claim not independently verified.

## 1. Which services lead in 2026 (incl. stream-focused and JP/KR market), and what do they cost?

### Takeaway
The general-purpose "long video → shorts" leaders in 2026 are OpusClip, Vizard, Klap, Submagic, Descript, Veed, CapCut and newcomer Reap (Munch has discontinued its standalone clipper); the streamer-focused tier is Eklipse, StreamLadder (ClipGPT), ClipMe, Spikes Studio, Medal and several small live-clippers. The biggest structural change in 2025-2026 is that the platforms themselves (YouTube Sep 2025, Twitch May 2026, CHZZK 2026) started auto-generating highlight clips, and in Korea/Japan small chat-reaction-based services (Captus, KIRARI) now target exactly the CHZZK/SOOP/VTuber niche stream2clip serves.

### Cited Findings

**General-purpose clippers — pricing (entry paid tier, annual unless noted)**
- Reap's 2026 benchmark (vendor report; Reap ranks itself #1) tested 9 paid tools with ~$3,000 spend on 6 source videos incl. a gaming stream; speed/accuracy measured April 2026, pricing/API re-checked Oct 30 2026. Entry prices: Reap $9.99/mo (Studio $29); OpusClip Starter $15/mo monthly-only, Pro $14.50/mo; Vizard Creator $14.50, Business $19.50; Submagic Starter $12, Pro $23, Business $41 (no free tier); Klap Basic $14, Pro $39, Pro+ $94; Descript Hobbyist $16, Creator $24, Business $50; Veed Creator $12.25/editor; CapCut Standard $9.99, Pro $19.99 (US); Munch standalone clipper discontinued (Pro was $49/mo in April), replaced by "Munch Studio" $38–60/mo — [Reap, State of AI Video Clipping 2026](https://reap.video/reports/state-of-top-ai-video-clipping-tools-2026)
- OpusClip pricing page (fetched): Free $0 / Starter $15/mo / Pro $29/mo / Business custom (monthly prices shown; Reap's $14.50 is annual). Free: watermark, media expires after 3 days, 10 GB upload cap. Starter: watermark-free, media expires after 29 days. Pro: 100 GB storage, team (2 seats per pack, up to 4 users), APIs. — [OpusClip Pricing](https://www.opus.pro/pricing)
- Reap benchmark timings (claims from a vendor test): time to first clip on a 90-min podcast — Reap 4–5 min, Submagic 8–12, Vizard ~10, Veed ~10–12, Munch 12–15, Klap ~15, Descript ~20, OpusClip Pro ~25. English caption accuracy ~98% for Reap/OpusClip/Vizard/Submagic/Descript, ~97% Klap; most tools ~95% in other languages — [Reap report](https://reap.video/reports/state-of-top-ai-video-clipping-tools-2026)
- Vizard: free tier 60 upload-min/month, 720p, watermark; Creator ~$14.50/mo annual ($29 monthly), Business ~$19.50 annual ($39 monthly) — [Plisio Vizard review (search snippet)](https://plisio.net/ai/vizard-ai); consistent with [Reap report](https://reap.video/reports/state-of-top-ai-video-clipping-tools-2026)
- Klap prices per clip, not per minute: $29/mo monthly for 100 clips, $79 for 300, $189 for 1,000 (yearly: $14/$39/$94); a $59 Pro price test reported — [Katto Klap alternatives (search snippet)](https://katto.tech/blog/best-klap-alternatives); a Nov 2026 review lists Basic $29 ($14 annual), Pro $79 ($39 annual) — [The Brand Hopper Klap review 2026](https://thebrandhopper.com/?p=29231)
- Submagic prices per member: $19/$39/$69 monthly or $12/$23/$41 yearly for 15/40/100 videos; clip detection ("Magic Clips") is reported as a paid add-on; 3 free videos — [PassiveShorts Submagic alternatives (search snippet)](https://passiveshorts.com/blog/submagic-alternatives/). Reap notes Submagic caps source video length by tier at 2, 5 or 30 min — [Reap report](https://reap.video/reports/state-of-top-ai-video-clipping-tools-2026)
- CapCut restructured pricing (Standard and Pro, top tier $19.99/mo) — [BIGVU CapCut free vs pro 2026](https://bigvu.tv/blog/capcut-free-vs-pro-what-2026s-restructure-actually-gives-you/); Reap calls CapCut's clipping "a side feature" with full auto-captions requiring a paid plan and no API/CLI/MCP/scheduler — [Reap report](https://reap.video/reports/state-of-top-ai-video-clipping-tools-2026)
- Clipchamp has no auto-clip feature (editing only; premium via Microsoft 365); Kapwing has a prompt-driven clip generator ("describe the highlights") with subtitles and smart framing — [Pictory OpusClip alternatives, Aug 2026](https://pictory.ai/blog/opusclip-alternatives); [Rework 2026 repurposing tools](https://resources.rework.com/tools/ai-video/best-ai-video-repurposing-tools-2026)

**Streamer-focused clippers**
- StreamLadder (prices "last verified Nov 16 2026"): Free $0 (720p/30fps, default layouts, watermark when paid features used); Starter $15/mo ($150/yr) — 1080p60, posting/scheduling to TikTok, YouTube, Instagram, Facebook; Creator $27/mo ($270/yr) — ClipGPT AI clipping, up to 30 clips per stream, Twitch + Kick import; Pro $39/mo ($390/yr) — team workspace for 2 editors, 4K60, posting to X. No credit/minute caps, "fair use" on ClipGPT; 7-day trial needs card — [StreamLadder Pricing](https://www.streamladder.com/pricing)
- Eklipse: Twitch, Kick, YouTube sources; paid ~$14.99/mo annual or $24.99/mo monthly (verified July 2026 on its own comparison page); clipping requires a paid plan; claims 3,000+ games with game-specific detection; Premium Pro adds Live Clipping, Posting Companion, Custom Highlights per game, private-stream processing — [Eklipse vs CrossClip (vendor page, July 2026)](https://eklipse.gg/compare/eklipse-vs-crossclip). Directories list "Premium from $19.99/mo" and free-plan limits of 15 highlights/stream, 720p, 14-day storage (vs 90 days paid) — [Eklipse blog](https://blog.eklipse.gg/eklipse-news-and-guide/is-eklipse-free-pricing-and-features-explained.html); [Capterra Eklipse pricing](https://www.capterra.com/p/10015243/Eklipse/pricing/) (sources conflict on price)
- ClipMe (vendor page dated Sep 1 2026): Free 100 clips from first stream; Pro $29/mo; one-time "Founding" $297; Studio (unpriced) with unlimited clips, keyword-triggered B-roll, sponsor detection, 3 seats. Claims live clipping from the HLS feed during broadcast on Kick/Twitch/YouTube and "~50 ranked clips from a 10-hour stream in ~5 min" — [ClipMe gaming clipper page](https://clipme.com/best-ai-clipper-for-gaming)
- Other live/stream clippers named in 2026 comparisons: Cut.pro (claims live clipping), klypra (watches a live Twitch stream; limited free plan), LumiClip (from €12.99/mo), StreamGen (free tier for a few Twitch streams/month), ViddyFlow — [klypra blog](https://klypra.app/blog/best-ai-tool-to-clip-twitch-streams); [LumiClip blog](https://www.lumiclip.ai/blog/best-ai-clipper-twitch-streamers); [ViddyFlow 2026 comparison](https://viddyflow.com/blog/best-ai-tools-to-turn-twitch-streams-into-clips-2026/) (all vendor-authored)
- Medal: auto-clipping via in-game event hooks across "100+ games"; pricing reports conflict ($3.99/mo Pro vs $9.99/mo Premium) — [Kompozy 2026 gaming clip roundup](https://kompozy.io/roundups/best-ai-gaming-clip-generators-2026); [Vidulk Powder vs Medal](https://www.vidulk.com/compare/powder-vs-medal)
- Powder (formerly a Windows AutoEdit app) is reported shut down / not available to new users, though one 2026 roundup still lists it — [Vidulk Powder vs Medal](https://www.vidulk.com/compare/powder-vs-medal) (conflicting)
- Spikes Studio: browser tool for Twitch VODs/podcasts → captioned clips; prices conflict (~$14/mo annual Pro+ vs $29/mo vs ~$19/mo) — [MakerStack Spikes Studio review 2026](https://makerstack.co/reviews/spikes-studio-review/). Sizzle: only a table mention ("auto process streams → highlights, compilations"), usage-based pricing — [Kompozy roundup](https://kompozy.io/roundups/best-ai-gaming-clip-generators-2026)

**Platform-native auto clipping (new competitors since 2025)**
- YouTube announced at Made on YouTube (Sep 2025) AI highlights that select the best moments from a livestream and turn them into Shorts — [TechCrunch, 2025-09-20](https://techcrunch.com/2025/09/20/updates-to-studio-youtube-live-new-gen-ai-tools-and-everything-else-announced-at-made-on-youtube); YouTube's creator-updates log (Oct 2025) says mobile livestreamers see a Short automatically pulled from the stream when it ends — [YouTube Help: Creator updates](https://support.google.com/youtube/answer/9072033). Made on YouTube 2026 coverage mentions a real-time livestream auto-dubbing test (EN/ES) — [Social Media Today](https://socialmediatoday.com/news/youtube-presents-new-ai-and-engagement-features-at-made-on-2026/831216)
- Twitch (per vendor Cut.pro summarizing official Twitch blog posts): "Auto Clips" announced at TwitchCon Rotterdam (post dated May 30 2026) scan chat activity, voice tone and on-screen events and generate captioned clips, moving into beta; auto captions on clips; "Dual Format" (Jun 17 2026) streams horizontal + vertical simultaneously and gives both versions of every clip and VOD; Twitch is "exploring" auto-crop/auto-trim — [Cut.pro, Twitch and clips in 2026](https://cut.pro/en/blog/twitch-wants-your-clips-2026) (official sources cited there: blog.twitch.tv/en/2026/05/30/..., blog.twitch.tv/en/2026/06/17/...)
- Kick: no built-in AI clipping found as of late 2026 (manual viewer clipping only) — [ClipSpeed Kick guide (vendor)](https://www.clipspeed.ai/ai-tools/kick-clip-generator.html)

**Korea**
- Naver CHZZK introduced "AI Clip" and "AI Chapter" (in-house system "Spotter", analyzing voice, captions and viewer reactions) during its 2026 World Cup broadcasts, generating ~3,400 AI clips (~30 per match), extended to the Asian Games and planned for LoL Worlds and entertainment events — [Digital Times](https://www.dt.co.kr/article/12085177); planned rollout to general (initially large) streamers — [Newsis, 2026-03-16](https://www.newsis.com/view/NISX20260316_0003550160)
- SOOP's AI manager "SARSA" automates broadcast settings, summaries, chat moderation; 2.0 beta lets AI "take over" the broadcast when the streamer is away — [Nate News, 2026-06-14](https://news.nate.com/view/20260614n01779); no SOOP-native auto-clip confirmed in these articles
- Captus (captus.kr): paste a CHZZK/SOOP replay link; highlights from chat-density peaks (per-minute chat graph, reaction score per clip); vertical drafts with title + editable subtitles, 15 templates; uploads to YouTube (multiple channels, public/unlisted/private); "routine" mode auto-analyzes every broadcast after it ends; free start, paid tiers not shown — [Captus](https://captus.kr/)
- Alphacut (AI highlight shorts) and ClipSpray also market Korean auto-shorts — [Alphacut](https://alphacut.video/); [ClipSpray KO blog](https://clipspray.ai/ko/blog) (not fetched; snippet only)

**Japan**
- KIRARI (Japanese VTuber-focused, vendor blog dated 2026-07-12): YouTube/Twitch archive URL → highlights from live-chat spikes + transcription → captioned vertical shorts editable in browser; Creator plan auto-analyzes new streams after they end with monthly cap; YouTube-only posting (unlisted/private/scheduled); free trial with no login (≤3 h video → top 2 shorts); paid from $9/mo — [KIRARI blog](https://www.kirari.io/blog/ai-clip-tools)
- Same KIRARI article rates OpusClip "△" for Japanese (captions/framing carry over poorly; "not suited to game-screen streams"), Vrew strong on JP captions but no highlight detection, 2short.ai ($9.90/mo, weaker JP captions), CapCut (no highlight detection) — [KIRARI blog](https://www.kirari.io/blog/ai-clip-tools)
- A desktop "VTuber kirinuki auto-creation software" called V-Cut was released via pixivFANBOX; details (local vs cloud, pricing) could not be retrieved — [V-Cut FANBOX post](https://sushino.fanbox.cc/posts/11418172); [V-Cut usage review](https://printemps.versus.jp/vtuber-kazakiyu/vcut/) (not fetched)
- Japanese 2026 articles note most general tools do not analyze chat, which is where VTuber humor lives — [VIBS blog (search snippet; page paywalled to fetch)](https://vibs.jp/blog/2026-06-10-2b513e1a)

### Inferences
- Pricing for "real" auto-clipping of streams clusters at $15–$39/month; stream-specific features (ClipGPT, Twitch/Kick import, live clipping) are consistently paywalled at the $25–$40 tier. A free, unlimited, local tool is a clear differentiator on cost, storage expiry (OpusClip 3/29-day expiry) and privacy.
- The most direct competitors to stream2clip are not OpusClip-type tools but Captus (KR, CHZZK/SOOP, chat-based) and KIRARI (JP, VTuber, live-chat-based), plus platform-native features (YouTube auto highlights, Twitch Auto Clips beta, CHZZK AI Clip). Platform-native features will likely commoditize "basic highlight from chat"; stream2clip's moat is VTuber-specific layout/avatar handling, agency guideline checks, multilingual subs, editability and local control.

### Gaps
- No primary pricing/feature pages fetched for Captions/Mirage, Riverside Magic Clips, Munch Studio, Spikes Studio, Sizzle, Medal; figures above come from secondary/affiliate sources and conflict.
- Twitch Auto Clips general-availability status and YouTube auto-highlight regional availability (incl. KR/JP) not confirmed from primary sources.
- Japanese low-cost tools (e.g., "ストクリ", V-Cut) and Korean Vrew 2026 shorts features not verified.

## 2. What features do they offer (especially 2025–2026 additions) that stream2clip lacks?

### Takeaway
Beyond detection and captions (where stream2clip is already competitive and in some respects ahead for VTubers — chat/superchat/heatmap signals and speaker-coloured captions, which OpusClip still lists as "coming soon"), commercial tools differentiate in 2025-26 on: LLM/multimodal "find anything" clipping and virality scores, AI headlines/hooks, AI B-roll/motion graphics, moving-object reframe, brand templates, dubbing (25–80+ languages), 9-platform scheduling/auto-posting, analytics, teams, APIs/MCP servers and AI agents, live clipping and automatic post-stream processing, game-event detection and voice-command clipping.

### Cited Findings

**OpusClip (market leader) — tiers and 2026 changelog**
- ClipAnything: Free/Starter clip on spoken words only; Pro/Business also on "visual objects, sound, emotion, genre curation". Virality score on Starter+. Reframe: Starter has genre model, dynamic layout, screenshare layout, custom reframing; Pro adds 1:1/16:9 and moving-object tracking. AI B-roll: Starter 3 AI images + 3 stock/mo; Pro 50 AI images/day, unlimited stock, AI video B-roll. Dubbing on Pro. Scheduler on 9 platforms on Pro (YouTube, TikTok, Instagram, Facebook, LinkedIn, X, Pinterest, Threads, Bluesky; Snapchat "coming soon"); Starter posts to Shorts/TikTok/IG without scheduler. Clip Analytics "coming soon" on Pro; Business has analytics + "real-time trend analysis". Pro: Video Editing, Scheduler and MCP APIs, Zapier, Premiere/DaVinci export, up to 4 brand templates, 2 custom fonts. Speaker-based caption colours listed as "coming soon" — [OpusClip Pricing](https://www.opus.pro/pricing)
- OpusClip changelog Sep–Oct 2026: Auto Headlines new styles + saveable to Brand Template (Oct 21); import audio from file/link into clip (Sep 30, Pro+); animated Name Tag/Location lower thirds, 12 presets (Sep 28); publishing to Pinterest/Threads/Bluesky with scheduling (Sep 28); Motion Studio generates B-roll animations and brand assets from images/video/audio/text prompts (Sep 18); official Claude connector (Sep 11); Speech Enhancement noise-reduction and voice-enhancement sliders (Sep 10); Brand Vocabulary — proper nouns transcribe correctly across clips (Sep 7); YouTube post can link the full video (Sep 4) — [OpusClip changelog](https://opusclip.canny.io/changelog)
- Gaming: OpusClip's gamer page describes a "Gameplay" layout (30% speaker top / 70% gameplay bottom) and a "Livestreamer" layout that detects facecam and gameplay separately and stacks them (claim) — [OpusClip for gamers](https://opus.pro/for-gamers); OpusClip says an upgraded ClipAnything picks "32.5% more relevant clips" and supports gaming, vlogs, music (claim) — [OpusClip 2-year blog](https://opus.pro/blog/celebrating-2-years-of-opusclip-from-the-best-ai-clipping-tool-to-the-best-ai-growth-tool-for-video-creators)
- A third-party review says OpusClip 4.0 was announced Nov 2 2026 with "Auto edit" for talking videos, Recipes, a Viral Hook template library, Motion Graphics and an "AI Producer" plugin — not confirmed on the official changelog — [BIGVU OpusClip review 2026](https://bigvu.tv/blog/opus-clip-tested-2026-where-ai-wins-40-percent-discard/). iOS app (Aug 2026 versions) added "No Caption" mode, Bluesky posting, caption stroke/shadow controls — [App Store](https://apps.apple.com/us/app/opusclip-ai-video-clipping/id6743615403)

**Other general clippers**
- Dubbing / API / MCP state (Oct 2026): Reap Creator has 80+ language dubbing, scheduling, REST API, MCP; OpusClip Pro 25-language dubbing, API (beta, capped), MCP with scheduling tools; Descript dubbing on AI credits, API, CLI, MCP, no scheduler; Submagic API + MCP (API can schedule), voice translation poorly documented; Klap API + MCP with scheduling, dubbing from Pro ($39) as of July 2026, source length up to 4 h; Vizard dubbing sold separately, no MCP, 40 transcription languages; Veed no scheduler/clipping API. "Five of the nine tools ship an official MCP server" — [Reap report](https://reap.video/reports/state-of-top-ai-video-clipping-tools-2026)
- Vizard Agent (beta, listed Aug 3 2026): prompt-driven "Video AGI" layer with AI post suggestions and direct publishing/scheduling — [EveryDev Vizard Agent](https://www.everydev.ai/tools/vizard-agent); [Stork Vizard Agent](https://www.stork.ai/en/vizard-agent). Vizard markets a per-clip virality score — [Vizard viral clip maker](https://vizard.ai/tools/ai-viral-clip-maker) (one competitor comparison says it has none; contested)
- Submagic: Magic Clips (20+ clips with hook titles, descriptions, cover image), Magic B-Rolls (reads transcript, auto-inserts stock B-roll; Storyblocks on Pro+), auto-zooms, AI hooks — [Submagic B-roll feature page](https://submagic.co/features/b-rolls); [Submagic AI video editor](https://www.submagic.co/ai-video-editor)
- Descript Oct/Nov 2026 updates: Animate Text (kinetic typography), Generative Layouts, cross-project media search ("type a phrase you remember and Descript finds the clip"; visual search Enterprise-only), Underlord Skills (AI co-editor that cuts filler, picks best takes, generates clips, all undoable) — [Descript updates Oct 2026](https://www.descript.com/blog/article/descript-updates-oct-2026); captions gradient fills (Aug 5 2026) — [Descript changelog](https://feedback.descript.com/changelog/release-round-upaugust-5th-2026); MCP integration — [Descript MCP](https://descript.com/integrations/mcp)
- Kapwing: prompt-based highlight description → clips — [Rework 2026](https://resources.rework.com/tools/ai-video/best-ai-video-repurposing-tools-2026)
- Captions (renamed Mirage in 2025 per a competitor article): AI Edit styles, Eye Contact correction, "Chat to Edit" — [search summary of DEV/competitor comparisons](https://dev.to/onsen/best-descript-alternatives-2026-top-tools-reviewed-hpd) (weak source, not primary)

**Stream-specific features**
- StreamLadder ClipGPT (Creator+): AI moment picking, auto-crop to vertical, facecam detection and framing, auto captions, hashtags and hooks, transcript search, "YouTube video from clips", Twitch/Kick import by link, up to 30 clips/stream; also Montage Maker, Schedule Maker, Emote Maker, mobile apps — [StreamLadder Pricing](https://www.streamladder.com/pricing)
- Eklipse: Auto Clipper processes every connected stream automatically; "Content Agent" makes clips/captions and posts to TikTok; Voice Command ("tell the AI which moments to clip"); AI-Edit adds memes to gaming clips; Content Publisher; game detection for 3,000+ games; Live Clipping and per-game Custom Highlights on Premium Pro; montage assembly with posts queued for approval (claims) — [Eklipse vs CrossClip](https://eklipse.gg/compare/eklipse-vs-crossclip); [Eklipse features](https://eklipse.gg/features/)
- ClipMe: chat velocity + "17 other proprietary signals"; live clipping from HLS (claims 28% of its clips came from live sessions); clips graded 1–31; face-tracked 9:16/1:1/16:9 incl. facecam+gameplay layouts; auto-translated word-level captions; brand kits; auto-posting to TikTok/Reels/Shorts on per-platform cadence; sponsor detection and keyword B-roll on Studio (claims) — [ClipMe](https://clipme.com/best-ai-clipper-for-gaming)
- Spikes Studio's "spike" trigger reportedly is a keyword mods type by hand, not automatic chat scoring (competitor claim) — [ClipMe](https://clipme.com/best-ai-clipper-for-gaming); a 2026 source says Spikes added real-time face detection for gameplay reactions — [MakerStack](https://makerstack.co/reviews/spikes-studio-review/)
- Medal: event-hook auto-clipping in 100+ games — [Kompozy](https://kompozy.io/roundups/best-ai-gaming-clip-generators-2026)
- Twitch Auto Clips (beta) and Dual Format vertical clips; YouTube auto Shorts from livestream; CHZZK AI Clip/Chapter — see Q1 sources ([Cut.pro](https://cut.pro/en/blog/twitch-wants-your-clips-2026), [TechCrunch](https://techcrunch.com/2025/09/20/updates-to-studio-youtube-live-new-gen-ai-tools-and-everything-else-announced-at-made-on-youtube), [Digital Times](https://www.dt.co.kr/article/12085177))
- Automatic post-stream processing is now standard in the KR/JP niche: Captus "routine" after each broadcast — [Captus](https://captus.kr/); KIRARI channel auto-analysis on Creator plans — [KIRARI](https://www.kirari.io/blog/ai-clip-tools)

**Feature gap matrix (stream2clip vs commercial)** — derived from the sources above
| Feature | Who has it (2025-26) | stream2clip |
|---|---|---|
| Chat-burst / superchat / heatmap detection | Captus, KIRARI, ClipMe, Twitch Auto Clips | Has (stronger signal set) |
| Speaker-coloured captions | OpusClip "coming soon" | Has |
| Multimodal / prompt "find anything" clipping (LLM) | OpusClip ClipAnything Pro, Kapwing, Vizard Agent | Lacks (no built-in LLM) |
| Virality / clip grade shown to user | OpusClip Starter+, ClipMe 1–31, Captus reaction score | Has internal scores; check UI exposure |
| AI headline / hook overlay styles, hook template library | OpusClip Auto Headlines (Oct 2026), Submagic, StreamLadder | Partial (titles, peak teaser, context line) |
| AI/stock B-roll, motion graphics | OpusClip, Submagic, ClipMe Studio | Lacks |
| Moving-object tracking reframe; real-face facecam detection | OpusClip Pro, StreamLadder, ClipMe, Spikes | Anime-face avatar box only |
| Brand templates/kits (saved caption/headline styles, fonts, logos) | OpusClip (1–4), ClipMe, CapCut Pro | Partial (presets) |
| Brand vocabulary for ASR | OpusClip (Sep 2026) | Glossary exists for translation only (verify) |
| Speech enhancement / noise reduction | OpusClip (Sep 2026), Descript | Lacks (has loudness normalization) |
| Animated lower thirds / name tags | OpusClip (Sep 2026) | Lacks |
| Kinetic typography / gradient captions / stroke+shadow | Descript (Aug–Nov 2026), OpusClip iOS | Karaoke only (check styles) |
| Voice dubbing | OpusClip 25 langs, Reap 80+, Klap Pro, Descript | Lacks |
| Multi-platform posting + scheduling | OpusClip 9 platforms, StreamLadder 5, Eklipse, ClipMe, Captus/KIRARI (YouTube) | YouTube only |
| Clip analytics / trend analysis | OpusClip Business (Pro "coming soon") | Lacks |
| Team workspace | OpusClip Pro, StreamLadder Pro, ClipMe Studio | Lacks |
| API / MCP / agent connectors | 5 of 9 tools ship MCP; OpusClip Claude connector | CLI + library only |
| Chat-to-edit / AI co-editor | Descript Underlord, Vizard Agent, Mirage | Lacks |
| Cross-project transcript/media search | Descript, StreamLadder ClipGPT | Lacks (verify) |
| Auto-run after each stream / channel watch | Eklipse, Captus, KIRARI | Lacks (manual) |
| Live clipping of HLS feed | ClipMe, Eklipse Pro, klypra, Cut.pro | OBS replay-buffer mode only (own stream) |
| Game-event (kill feed) detection | Eklipse 3,000+ games, Medal 100+ | Lacks |
| Voice-command clipping | Eklipse | Partial (streamer markers) |
| Premiere/DaVinci project export | OpusClip Pro | EDL/markers (check XML) |
| Meme/sticker auto-insertion | Eklipse AI-Edit | Lacks (has SFX) |
| Sponsor detection | ClipMe Studio | Lacks |

### Inferences
- The highest-value gaps for a VTuber/stream tool (not podcast tool) appear to be: (1) automatic post-stream processing / channel watching, (2) multi-platform export/posting beyond YouTube, (3) optional LLM layer (semantic selection, hook/title rewriting, chat-to-edit), (4) speech enhancement + ASR custom vocabulary, (5) richer caption/hook styling and brand templates, (6) MCP/agent interface on top of the existing CLI, (7) clip performance feedback (analytics) to tune detection weights. AI B-roll and dubbing matter less for VTuber kirinuki (avatar + game screen is already the visual), and voice dubbing of a VTuber's voice raises agency/consent issues.
- stream2clip already exceeds several leaders on VTuber-relevant specifics (avatar-aware stacking, superchat/heatmap signals, speaker colours, agency guideline checks), which commercial reviewers say general tools handle poorly (see Q3).

### Gaps
- Exact launch dates for OpusClip ClipAnything/ReframeAnything, Vizard virality score, Submagic Magic B-roll were not found.
- No source verified how any commercial reframer handles Live2D/3D VTuber avatars specifically.
- OpusClip 4.0 (Nov 2026) details unverified from primary source.

## 3. What do users complain about (G2, Trustpilot, Reddit, reviews)?

### Takeaway
The recurring complaints are: low hit rate (many generated clips are unusable), clips with awkward starts/ends, credit/minute billing that feels opaque or double-counted, credits lost on failed jobs, clip expiry, outages, hard cancellation, caption misalignment, and tools tuned for single-talking-head podcasts that mis-frame facecam/gameplay or fail on Japanese/game-screen streams.

### Cited Findings
- OpusClip G2: "It can be 10 clips but only like 3 clips" are good; awkward start/end on some clips; captions inaccurate for some words; speech enhancement limited to 10 clips/day — [G2 OpusClip reviews](https://www.g2.com/products/opusclip)
- OpusClip Product Hunt: TikTok repeatedly rejected videos uploaded directly from OpusClip, while manual upload of the same file worked — [Product Hunt OpusClip reviews](https://www.producthunt.com/products/opus-clip/reviews)
- OpusClip Trustpilot: TrustScore ~4/5 (~360 reviews on one regional page); complaints that billing is based on "time AND credits at the same time", credit refund for deleted videos is "very hidden", projects can disappear after subscription ends, outages "every couple of days", jobs stuck during outages consume credits to restart, "AI seems to get worse after buying credits"; mixed support (some got credits restored, one was told only to cancel) — [Trustpilot opus.pro p2](https://www.trustpilot.com/review/opus.pro?page=2); [Trustpilot opus.pro p7](https://www.trustpilot.com/review/opus.pro?page=7); [Trustpilot IE](https://ie.trustpilot.com/review/opus.pro)
- A 2026 OpusClip review is titled around "40 percent discard" (i.e., a large share of clips discarded) — [BIGVU](https://bigvu.tv/blog/opus-clip-tested-2026-where-ai-wins-40-percent-discard/) (title/slug only; body not fetched)
- Reddit feedback summarized by a competitor: AI "gives some decent ideas" but "often misses the point" — [eesel OpusClip reviews](https://www.eesel.ai/blog/opusclip-reviews) (competitor-authored)
- OpusClip for streams: "tuned for podcasts", auto-reframe assumes one talking head, streamers report it locking onto the wrong pane with a facecam; Kick support is URL import only (competitor claims) — [ClipMe](https://clipme.com/best-ai-clipper-for-gaming). KIRARI: OpusClip "assumes face-on-camera talking format, not suited to game-screen streams", Japanese captions/framing △ (competitor claim) — [KIRARI](https://www.kirari.io/blog/ai-clip-tools)
- Klap Trustpilot (2025–26): unable to cancel, upgrade pop-ups on renewal, hard to reach human support, slow editing, "captions never seem to align right"; positives on output quality and editor — [Trustpilot Klap (CA)](https://ca.trustpilot.com/review/klap.app); editorial 3.9/5, "works best with speech-heavy content" — [Dupple Klap](https://www.dupple.com/tools/klap-ai)
- Vizard: Capterra "Good not Great" 7/10, "costly but does the job"; a review cites a 30–40% clip miss rate (April 2026) — [Capterra Vizard reviews](https://www.capterra.com/p/10009818/Vizard/reviews/); [FluxNote Vizard review 2026](https://fluxnote.io/guides/vizard-ai-video-review-2026)
- Submagic: reviewer found auto-added B-roll sometimes did not fit what was being said; premium B-roll/clean audio only on higher tiers — reported in 2026 Submagic reviews ([Filmora Submagic review](https://filmora.wondershare.com/video-editor-review/submagic-review.html); exact outlet for the quote not pinned down in search results)
- StreamLadder: a Reddit thread "StreamLadder Just Priced Out Normal Streamers" reflects pricing frustration; common r/Twitch setup is Eklipse for overnight detection + StreamLadder free editor for formatting — [TwoAverageGamers 2026 roundup](https://www.twoaveragegamers.com/best-ai-clip-detection-tools-for-streamers-2026/)
- Eklipse misses hype moments without a kill; gameplay-event tools ignore funny fails/pure reactions; Eklipse "never reads chat" and renders only after session ends (competitor claims) — [ClipMe](https://clipme.com/best-ai-clipper-for-gaming); [TwoAverageGamers](https://www.twoaveragegamers.com/best-ai-clip-detection-tools-for-streamers-2026/)
- Limits that users hit: OpusClip free media expires in 3 days, Starter in 29 days; Submagic source length caps 2/5/30 min; Descript AI features on monthly credits; OpusClip API beta and capped — [OpusClip Pricing](https://www.opus.pro/pricing); [Reap report](https://reap.video/reports/state-of-top-ai-video-clipping-tools-2026)
- Japanese articles: general tools do not analyze chat, which matters most for VTuber streams; highlights "still need human judgment" even for chat-based KIRARI — [KIRARI](https://www.kirari.io/blog/ai-clip-tools); [VIBS (snippet)](https://vibs.jp/blog/2026-06-10-2b513e1a)

### Inferences
- A local tool avoids the most emotionally charged complaints (credits, expiry, outages, cancellation). The complaints stream2clip should still pre-empt are quality ones: hit rate, clip boundaries (start/end), caption timing, and framing of facecam/avatar + game.
- "Hit rate" complaints suggest stream2clip should show why each clip was chosen (signal breakdown) and make bulk accept/reject fast; this is cheaper than trying to be more accurate than cloud models.

### Gaps
- Could not access Reddit threads directly (r/NewTubers, r/Twitch, r/VirtualYoutubers); no VTuber-specific user complaints about commercial reframing of avatars were found.
- No G2/Trustpilot data gathered for Eklipse, StreamLadder, Captus, KIRARI.

## 4. Which features are realistic for a free, local, privacy-respecting desktop tool vs needing cloud?

### Takeaway
Most differentiating 2025–26 features are implementable locally (auto post-stream watching, ASR vocabulary, speech enhancement, styling/brand templates, lower thirds, transcript search, NLE export, MCP wrapper, voice-command markers, object-tracking reframe, optional local LLM); multi-platform posting and analytics are possible locally only through each platform's official API with the user's own OAuth; team workspaces, generative AI B-roll at scale, real-time trend analysis and always-on live clipping are inherently cloud-shaped.

### Cited Findings
- Commercial vendors gate the "local-feasible" features behind paid tiers: e.g., OpusClip Brand Vocabulary, Speech Enhancement sliders, lower thirds (2026 changelog), Premiere/DaVinci export (Pro), moving-object tracking (Pro) — [OpusClip changelog](https://opusclip.canny.io/changelog); [OpusClip Pricing](https://www.opus.pro/pricing)
- The MCP/agent interface is becoming table stakes: 5 of 9 benchmarked tools ship an MCP server (Oct 2026); Reap even includes MCP in its free plan; OpusClip MCP added scheduling tools; Descript ships API + CLI + MCP — [Reap report](https://reap.video/reports/state-of-top-ai-video-clipping-tools-2026); [Descript MCP](https://descript.com/integrations/mcp)
- Automatic post-stream processing (Captus routine, KIRARI channel auto-analysis, Eklipse Auto Clipper) is implemented server-side by those vendors — [Captus](https://captus.kr/); [KIRARI](https://www.kirari.io/blog/ai-clip-tools); [Eklipse](https://eklipse.gg/compare/eklipse-vs-crossclip)
- Live clipping from the HLS feed (ClipMe, Eklipse Pro) runs on vendor servers during the broadcast — [ClipMe](https://clipme.com/best-ai-clipper-for-gaming)
- Platforms now provide vertical versions natively (Twitch Dual Format gives both horizontal and vertical clips/VODs) — [Cut.pro summary of Twitch blog](https://cut.pro/en/blog/twitch-wants-your-clips-2026)
- Multi-platform posting in commercial tools spans YouTube, TikTok, Instagram, Facebook, LinkedIn, X, Pinterest, Threads, Bluesky (OpusClip) — [OpusClip Pricing](https://www.opus.pro/pricing)

### Inferences
Feasibility tiers for stream2clip (engineering judgement, not sourced):
- **Local, low cost, high value:**
  - Channel/VOD watcher that auto-runs the pipeline when a new VOD/archive appears (YouTube, Twitch, CHZZK, SOOP polling) — matches Captus/KIRARI/Eklipse automation without a server; runs while the PC is on.
  - ASR custom vocabulary: feed the existing glossary into faster-whisper as initial prompt / hotwords (OpusClip's Brand Vocabulary equivalent).
  - Speech enhancement / denoise via open models (e.g., RNNoise/DeepFilterNet class) before ASR and in export.
  - Caption style system: stroke/shadow/gradient, keyword highlight, emoji insertion, kinetic presets; saved "brand templates" (fonts, colours, logo, headline style) per channel.
  - Hook/headline overlay templates and animated name-tag lower thirds (e.g., VTuber name + collab partner).
  - Explainable clip score in UI (signal breakdown) as a "virality score" equivalent; faster bulk accept/reject.
  - Cross-VOD transcript + chat search library ("find every time X said Y").
  - Premiere/DaVinci/FCPXML export in addition to EDL.
  - MCP server / JSON-RPC wrapper over the existing CLI/library so external agents can drive it locally.
  - Voice-command markers detected from transcript ("clip that", "切り抜いて", "클립") complementing streamer markers.
  - Sponsor/ad-read detection from transcript keywords (to exclude or tag).
  - Generic object tracking for gameplay crop (OpenCV trackers) and real-face facecam detection for non-VTuber streamers.
- **Local but heavy / optional download:**
  - Local LLM (llama.cpp/Ollama class) for semantic clip selection, title/hook rewriting in KO/JA/EN, chat-to-edit; or "bring your own API key" plugin, consistent with the existing translation plugin model.
  - Active-speaker detection for multi-person real-face collabs (audio-visual models) — CPU/GPU cost.
  - Local TTS dubbing — technically possible but voice cloning a VTuber's voice conflicts with agency guidelines; better framed as subtitle translation (already present).
  - Game-event detection — per-game vision models; low priority for chat-driven VTuber content.
- **Needs platform APIs (local app can call them with user OAuth):**
  - Posting/scheduling to TikTok, Instagram Reels, X, Threads, Bluesky; each needs developer app registration/review, so maintenance burden is the real cost, not compute.
  - Clip analytics via YouTube Analytics API for clips stream2clip uploaded, used locally to re-weight detection signals per channel (a feedback loop none of the reviewed vendors clearly offers beyond OpusClip Business "trend analysis").
- **Inherently cloud / out of scope for a free local tool:**
  - Team workspace with shared storage and permissions (could be approximated with shareable project files).
  - Generative AI video B-roll at scale and licensed stock libraries (Storyblocks-type licensing).
  - Real-time cross-creator trend analysis.
  - 24/7 live clipping of streams when the user's PC is off.

### Gaps
- No sources gathered here on specific open-source models' quality for these local implementations (presumably covered by the OSS-comparison researcher).
- Platform API approval requirements (TikTok Content Posting API audit, Instagram Graph API business-account requirement) were not researched in this pass.
