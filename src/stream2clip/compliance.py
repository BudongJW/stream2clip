"""Agency secondary-creation (切り抜き / 클립) guideline helpers.

Profiles encode the rules found in the reference research (as of 2026-11).
They are a checklist, not legal advice: guidelines change and every talent may
add their own rules, so always read the linked original before publishing.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .sources import SourceInfo

__all__ = ["AgencyProfile", "Issue", "PROFILES", "build_description", "check_upload", "get_profile"]


@dataclass(frozen=True)
class AgencyProfile:
    key: str
    name: str
    guideline_url: str = ""
    revised: str | None = None
    source_link_required: bool = True
    source_on_top: bool = False
    registration: str = "none"  # none | recommended | required
    members_only_forbidden: bool = True
    before_archive_forbidden: bool = False
    content_id_forbidden: bool = False
    ai_label_required: bool = False
    permission_number: bool = False
    notes: tuple[str, ...] = field(default_factory=tuple)


PROFILES: dict[str, AgencyProfile] = {
    "hololive": AgencyProfile(
        key="hololive",
        name="hololive production (COVER)",
        guideline_url="https://hololivepro.com/terms/",
        revised="2026-08-31",
        source_on_top=True,
        registration="recommended",
        before_archive_forbidden=True,
        content_id_forbidden=True,
        notes=("멤버십, 유료 콘텐츠 사용 금지", "탤런트 음성으로 음성 생성(AI 보이스) 금지", "등록 채널은 삭제 요청 전에 연락을 받음"),
    ),
    "nijisanji": AgencyProfile(
        key="nijisanji",
        name="にじさんじ (ANYCOLOR)",
        guideline_url="https://www.anycolor.co.jp/guidelines/en/",
        revised="2025-05-23",
        registration="required",
        notes=("오해를 부르는 편집, 내용과 동떨어진 썸네일 금지", "삭제 요청에는 즉시 응해야 함", "범위를 넘는 수익화는 사전 승인", "라이버별 추가 규칙 확인"),
    ),
    "vspo": AgencyProfile(
        key="vspo",
        name="ぶいすぽっ!",
        guideline_url="https://vspo.jp/en/guide/",
        revised="2026-09-17",
        permission_number=True,
        registration="required",
        notes=(
            "영상 클립은 사전 신청 및 허가 필요, 설명란에 원본 URL과 발급받은 허가 번호 표기",
            "방송 종료 후 YouTube는 1시간, Twitch는 24시간 지난 뒤 게시",
            "노래 방송, 3D 라이브의 노래 부분 전재 금지",
            "원본을 잘라 붙이기만 한(창작성이 없는) 영상 금지",
        ),
    ),
    "aogiri": AgencyProfile(
        key="aogiri",
        name="あおぎり高校",
        revised="2026-02",
        ai_label_required=True,
        notes=("생성형 AI 2차 창작물은 #AIイラスト 등 AI 사용 표기 필요", "무편집 재업로드, 공식 오인 작품 금지"),
    ),
    "generic": AgencyProfile(
        key="generic",
        name="개인 / 기타 기획사",
        notes=("해당 버튜버와 기획사의 2차 창작 가이드라인을 직접 확인하세요",),
    ),
}


def get_profile(key: str | None) -> AgencyProfile:
    if not key:
        return PROFILES["generic"]
    try:
        return PROFILES[key.lower()]
    except KeyError as exc:
        raise ValueError(f"Unknown agency {key!r}; choose one of {', '.join(PROFILES)}") from exc


@dataclass(frozen=True)
class Issue:
    level: str  # error | warning | info
    message: str

    def __str__(self) -> str:
        icon = {"error": "x", "warning": "!", "info": "-"}.get(self.level, "-")
        return f"{icon} {self.message}"


def _clock(seconds: float) -> str:
    seconds = max(0, int(seconds))
    h, m, s = seconds // 3600, seconds % 3600 // 60, seconds % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def build_description(
    source: SourceInfo,
    profile: AgencyProfile | None = None,
    *,
    start: float | None = None,
    end: float | None = None,
    summary: str = "",
    uses_ai: bool = False,
    permission_number: str | None = None,
    hashtags: tuple[str, ...] = (),
) -> str:
    """Video description with the source credit first (as hololive requires) and required labels."""
    profile = profile or PROFILES["generic"]
    lines: list[str] = []
    if source.url or source.title:
        lines.append("【元配信 / 원본 방송】")
        if source.title:
            lines.append(source.title)
        link = source.timestamp_url(start) if start is not None and source.url else source.url
        if link:
            lines.append(link)
        if source.channel:
            lines.append(f"{source.channel}" + (f"  {source.channel_url}" if source.channel_url else ""))
        if start is not None and end is not None:
            lines.append(f"({_clock(start)} ~ {_clock(end)})")
        lines.append("")
    if permission_number:
        lines += [f"許諾番号 / 허가 번호: {permission_number}", ""]
    if summary:
        lines += [summary, ""]
    if uses_ai:
        lines += ["자동 자막, 하이라이트 검출 등 AI 도구를 사용해 편집했습니다." + (" #AI" if profile.ai_label_required else ""), ""]
    if hashtags:
        lines.append(" ".join(t if t.startswith("#") else f"#{t}" for t in hashtags))
    return "\n".join(lines).strip() + "\n"


def check_upload(
    source: SourceInfo,
    profile: AgencyProfile | None = None,
    *,
    description: str | None = None,
    registered: bool | None = None,
    uses_ai: bool = False,
    uses_voice_generation: bool = False,
    content_id: bool = False,
    permission_number: str | None = None,
) -> list[Issue]:
    """Pre-upload checklist. ``error`` = violates the profile, ``warning`` = needs attention."""
    profile = profile or PROFILES["generic"]
    issues: list[Issue] = []
    if profile.members_only_forbidden and source.members_only:
        issues.append(Issue("error", "멤버십, 유료 한정 방송은 클립으로 쓸 수 없습니다."))
    if profile.before_archive_forbidden and not source.archive_public:
        issues.append(Issue("error", "원본 아카이브가 공개되기 전(라이브 중, 예정, 비공개)에는 게시할 수 없습니다."))
    if profile.content_id_forbidden and content_id:
        issues.append(Issue("error", "클립을 Content ID에 등록하면 안 됩니다."))
    if profile.key == "hololive" and uses_voice_generation:
        issues.append(Issue("error", "탤런트 음성으로 음성을 생성(AI 보이스)하는 것은 금지되어 있습니다."))
    if profile.source_link_required:
        if not source.url:
            issues.append(Issue("error", "원본 방송 URL이 없습니다. 설명란에 원본 링크를 넣어야 합니다."))
        elif description is not None:
            if source.url.split("?")[0] not in description:
                issues.append(Issue("error", "설명란에 원본 방송 URL이 없습니다."))
            elif profile.source_on_top:
                head = "\n".join(description.strip().splitlines()[:4])
                if source.url.split("?")[0] not in head:
                    issues.append(Issue("error", "원본 URL과 제목을 설명란 맨 위에 두어야 합니다."))
    if profile.registration == "required" and registered is not True:
        issues.append(Issue("error" if registered is False else "warning", f"{profile.name}: 클립 채널 사전 등록이 필요합니다."))
    elif profile.registration == "recommended" and registered is not True:
        issues.append(Issue("warning", f"{profile.name}: 클립 채널 등록을 권장합니다."))
    if profile.permission_number and not permission_number:
        issues.append(Issue("warning", "발급받은 허가 번호(許諾番号)를 설명란에 표기해야 합니다."))
    if profile.ai_label_required and uses_ai and (description is None or "AI" not in description):
        issues.append(Issue("error", "AI를 사용한 2차 창작물에는 AI 사용 표기가 필요합니다."))
    for note in profile.notes:
        issues.append(Issue("info", note))
    if profile.guideline_url:
        issues.append(Issue("info", f"가이드라인 원문 확인: {profile.guideline_url}" + (f" (개정 {profile.revised})" if profile.revised else "")))
    return issues
