package io.github.budongjw.stream2clip

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class CoreTest {
    @Test
    fun readsWhatTheBridgeWrites() {
        val text = """
            {"source": {"url": "https://chzzk.naver.com/video/16230061", "title": "방송", "channel": "버튜버 독케익", "duration": 16791.0,
                        "stream_date": "20261117", "category": "Gaming", "game": "명조:워더링 웨이브", "platform": "chzzk"},
             "stream": {"url": "https://x/v.m3u8", "height": 720, "protocol": "m3u8_native", "headers": {"Referer": "https://chzzk.naver.com/"}},
             "form": "shorts", "messages": 23, "note": "",
             "clips": [{"rank": 1, "start": 1800.0, "end": 1890.0, "peak": 1830.0, "score": 9.5, "reasons": ["채팅 급증"],
                        "title": "[독케익] 방송", "caption": "방송", "hashtags": ["#독케익", "#버튜버"], "description": "원본 방송\n", "link": "https://chzzk.naver.com/video/16230061?currentTime=1800"},
                       {"rank": 2, "start": 10.0, "end": 40.0, "peak": 20.0, "score": 3.0, "reasons": [],
                        "title": "[독케익] 다른 순간", "hashtags": [], "description": "", "link": ""}]}
        """
        val found = parseAnalysis(text)
        assertEquals("방송", found.clips[0].caption)
        assertEquals("[독케익] 다른 순간", found.clips[1].caption) // an older bridge without words for the video: the title
        assertEquals("chzzk", found.source.platform)
        assertEquals("명조:워더링 웨이브", found.source.game)
        assertEquals(mapOf("Referer" to "https://chzzk.naver.com/"), found.stream?.headers)
        assertEquals(90.0, found.clips.first().length, 0.001)
        assertEquals(listOf("#독케익", "#버튜버"), found.clips.first().hashtags)
    }

    @Test
    fun noStreamAndNoDate() {
        val found = parseAnalysis(
            """{"source": {"url": "u", "title": "", "channel": "", "duration": null, "stream_date": null, "category": "", "game": "", "platform": ""},
                "stream": null, "form": "clip", "messages": 0, "clips": [], "note": "login required"}""",
        )
        assertNull(found.stream)
        assertNull(found.source.streamDate)
        assertNull(found.source.duration)
        assertEquals("login required", found.note)
    }

    @Test
    fun clockLikeTheDesktop() {
        assertEquals("0:05", clock(5.9))
        assertEquals("30:00", clock(1800.0))
        assertEquals("1:02:03", clock(3723.0))
        assertEquals("0:00", clock(-3.0))
    }
}
