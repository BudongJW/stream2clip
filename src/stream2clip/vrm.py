"""What a VRM avatar's licence allows: read the meta of a ``.vrm`` file and check a planned use against it.

A VRM model carries its terms of use in the file itself, in a form a program can read:
who may wear the avatar, whether money may be made with it, whether a credit is due.
Both layouts are understood - VRM 1.0 (``extensions.VRMC_vrm.meta``) and VRM 0.x
(``extensions.VRM.meta``, whose keys are spelled ``...UssageName``) - and brought to the
terms of 1.0. Only the JSON chunk of the file is read: nothing here needs a 3D library.

Like the agency profiles this is a checklist, not legal advice: the meta is what the
author of the model filled in, and a model can come with further terms on its sales page.
"""

from __future__ import annotations

import json
import os
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .compliance import Issue
from .i18n import mark, shown, tr

__all__ = ["VrmMeta", "read_vrm_meta", "vrm_meta_from_json", "check_vrm"]

_GLB_MAGIC, _JSON_CHUNK = 0x46546C67, 0x4E4F534A
_USERS_0 = {"OnlyAuthor": "onlyAuthor", "ExplicitlyLicensedPerson": "onlySeparatelyLicensedPerson", "Everyone": "everyone"}
_PERMISSIONS = {"onlyAuthor": mark("제작자 본인만"), "onlySeparatelyLicensedPerson": mark("별도 허락을 받은 사람만"), "everyone": mark("누구나")}
_COMMERCIAL = {"personalNonProfit": mark("개인의 비영리 사용만"), "personalProfit": mark("개인의 영리 사용까지"), "corporation": mark("법인 사용까지")}
_MODIFICATION = {"prohibited": mark("개변 금지"), "allowModification": mark("개변 허용"), "allowModificationRedistribution": mark("개변 및 개변본 재배포 허용")}


@dataclass(frozen=True)
class VrmMeta:
    """The terms of a model in the vocabulary of VRM 1.0. ``None`` / ``""`` = the file does not say."""

    spec: str  # "1.0" or "0.x"
    name: str = ""
    authors: tuple[str, ...] = ()
    avatar_permission: str = ""  # onlyAuthor | onlySeparatelyLicensedPerson | everyone
    commercial_usage: str = ""  # personalNonProfit | personalProfit | corporation
    credit_required: bool | None = None
    redistribution: bool | None = None
    modification: str = ""  # prohibited | allowModification | allowModificationRedistribution
    violent: bool | None = None
    sexual: bool | None = None
    political: bool | None = None
    antisocial: bool | None = None
    license: str = ""
    other_license_url: str = ""

    def summary(self) -> list[str]:
        """The terms in a few lines, for a person to read."""
        unstated = tr("기재 없음")

        def yes_no(value: bool | None) -> str:
            return unstated if value is None else (tr("허용") if value else tr("불가"))

        name = self.name or tr("(이름 없음)")
        credit = unstated if self.credit_required is None else (tr("필요") if self.credit_required else tr("불필요"))
        lines = [
            tr("모델: {0}, 제작자 {1} (VRM {2})").format(name, ", ".join(self.authors), self.spec) if self.authors else tr("모델: {0} (VRM {1})").format(name, self.spec),
            tr("아바타 사용: {0}").format(shown(_PERMISSIONS[self.avatar_permission]) if self.avatar_permission in _PERMISSIONS else unstated),
            tr("영리 사용: {0}").format(shown(_COMMERCIAL[self.commercial_usage]) if self.commercial_usage in _COMMERCIAL else unstated),
            tr("크레딧 표기: {0}").format(credit),
            tr("개변: {0}, 재배포: {1}").format(shown(_MODIFICATION[self.modification]) if self.modification in _MODIFICATION else unstated, yes_no(self.redistribution)),
            tr("폭력 표현: {0}, 성적 표현: {1}, 정치 및 종교: {2}, 반사회 및 혐오: {3}").format(yes_no(self.violent), yes_no(self.sexual), yes_no(self.political), yes_no(self.antisocial)),
        ]
        if self.license:
            lines.append(tr("라이선스: {0}").format(self.license))
        if self.other_license_url:
            lines.append(tr("추가 조건: {0}").format(self.other_license_url))
        return lines


def _json_chunk(path: Path) -> dict[str, Any]:
    with path.open("rb") as fh:
        head = fh.read(12)
        if len(head) < 12 or struct.unpack("<I", head[:4])[0] != _GLB_MAGIC:
            raise ValueError(f"Not a VRM file (a VRM is a binary glTF): {path.name}")
        length, kind = struct.unpack("<II", fh.read(8))
        if kind != _JSON_CHUNK:
            raise ValueError(f"Not a VRM file (the first chunk is not JSON): {path.name}")
        data = json.loads(fh.read(length).decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Not a VRM file (unexpected JSON): {path.name}")
    return data


def vrm_meta_from_json(gltf: dict[str, Any]) -> VrmMeta:
    """The meta of a parsed glTF document; ``ValueError`` when it is a plain glTF without VRM terms."""
    extensions = gltf.get("extensions") or {}
    if isinstance((extensions.get("VRMC_vrm") or {}).get("meta"), dict):
        m = extensions["VRMC_vrm"]["meta"]
        credit = m.get("creditNotation")
        return VrmMeta(
            spec="1.0", name=str(m.get("name") or ""), authors=tuple(str(a) for a in m.get("authors") or ()),
            avatar_permission=str(m.get("avatarPermission") or ""), commercial_usage=str(m.get("commercialUsage") or ""),
            credit_required=None if credit is None else credit == "required",
            redistribution=m.get("allowRedistribution"), modification=str(m.get("modification") or ""),
            violent=m.get("allowExcessivelyViolentUsage"), sexual=m.get("allowExcessivelySexualUsage"),
            political=m.get("allowPoliticalOrReligiousUsage"), antisocial=m.get("allowAntisocialOrHateUsage"),
            license=str(m.get("licenseUrl") or ""), other_license_url=str(m.get("otherLicenseUrl") or ""),
        )
    if isinstance((extensions.get("VRM") or {}).get("meta"), dict):
        m = extensions["VRM"]["meta"]

        def allowed(key: str) -> bool | None:
            return None if m.get(key) is None else m.get(key) == "Allow"

        # 0.x names a licence instead of separate switches: Creative Commons BY asks for a credit,
        # NC rules out commercial use, ND rules out changes.
        licence = str(m.get("licenseName") or "")
        parts = licence.split("_")[1:] if licence.startswith("CC_") else []
        commercial = allowed("commercialUssageName")
        if "NC" in parts:
            commercial = False
        return VrmMeta(
            spec="0.x", name=str(m.get("title") or ""), authors=(str(m["author"]),) if m.get("author") else (),
            avatar_permission=_USERS_0.get(str(m.get("allowedUserName") or ""), ""),
            commercial_usage="" if commercial is None else ("corporation" if commercial else "personalNonProfit"),
            credit_required=True if "BY" in parts else (False if licence == "CC0" else None),
            redistribution=False if licence == "Redistribution_Prohibited" else (True if licence.startswith("CC") else None),
            modification="prohibited" if "ND" in parts else ("allowModificationRedistribution" if licence.startswith("CC") else ""),
            violent=allowed("violentUssageName"), sexual=allowed("sexualUssageName"),
            license=licence, other_license_url=str(m.get("otherLicenseUrl") or m.get("otherPermissionUrl") or ""),
        )
    raise ValueError("This glTF has no VRM meta: it is not a VRM model")


def read_vrm_meta(path: str | os.PathLike[str]) -> VrmMeta:
    return vrm_meta_from_json(_json_chunk(Path(path)))


def check_vrm(meta: VrmMeta, *, monetized: bool = False, corporation: bool = False) -> list[Issue]:
    """Findings for using the avatar in clips: ``monetized`` = the channel earns money, ``corporation`` = it is run by a company."""
    issues: list[Issue] = []
    if meta.avatar_permission == "onlyAuthor":
        issues.append(Issue("warning", tr("제작자 본인만 사용할 수 있는 모델입니다. 제작자가 아니면 사용할 수 없습니다.")))
    elif meta.avatar_permission == "onlySeparatelyLicensedPerson":
        issues.append(Issue("warning", tr("별도 허락을 받은 사람만 사용할 수 있는 모델입니다. 허락 여부를 확인해야 합니다.")))
    elif not meta.avatar_permission:
        issues.append(Issue("warning", tr("아바타 사용 허용 범위가 파일에 기재되어 있지 않습니다. 배포처의 약관을 확인해야 합니다.")))
    if corporation and meta.commercial_usage in ("personalNonProfit", "personalProfit"):
        issues.append(Issue("error", tr("법인이 사용할 수 없는 모델입니다 (허용 범위: {0}).").format(shown(_COMMERCIAL[meta.commercial_usage]))))
    elif monetized and meta.commercial_usage == "personalNonProfit":
        issues.append(Issue("error", tr("수익을 얻는 채널에서 사용할 수 없는 모델입니다 (허용 범위: 개인의 비영리 사용만).")))
    elif (monetized or corporation) and not meta.commercial_usage:
        issues.append(Issue("warning", tr("영리 사용 허용 여부가 파일에 기재되어 있지 않습니다. 배포처의 약관을 확인해야 합니다.")))
    if meta.credit_required:
        credit = " / ".join(part for part in (meta.name, ", ".join(meta.authors)) if part)
        issues.append(Issue("warning", tr("크레딧 표기가 필요합니다: {0}").format(credit) if credit else tr("크레딧 표기가 필요합니다.")))
    if meta.other_license_url:
        issues.append(Issue("info", tr("추가 조건 확인: {0}").format(meta.other_license_url)))
    if meta.spec == "0.x":
        issues.append(Issue("info", tr("VRM 0.x 메타는 영리 사용을 허용과 불가로만 구분합니다. 개인과 법인의 구분은 배포처의 약관에서 확인해야 합니다.")))
    return issues
