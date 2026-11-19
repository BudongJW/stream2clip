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

__all__ = ["VrmMeta", "read_vrm_meta", "vrm_meta_from_json", "check_vrm"]

_GLB_MAGIC, _JSON_CHUNK = 0x46546C67, 0x4E4F534A
_USERS_0 = {"OnlyAuthor": "onlyAuthor", "ExplicitlyLicensedPerson": "onlySeparatelyLicensedPerson", "Everyone": "everyone"}
_PERMISSIONS = {"onlyAuthor": "제작자 본인만", "onlySeparatelyLicensedPerson": "별도 허락을 받은 사람만", "everyone": "누구나"}
_COMMERCIAL = {"personalNonProfit": "개인의 비영리 사용만", "personalProfit": "개인의 영리 사용까지", "corporation": "법인 사용까지"}
_MODIFICATION = {"prohibited": "개변 금지", "allowModification": "개변 허용", "allowModificationRedistribution": "개변 및 개변본 재배포 허용"}


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
        def yes_no(value: bool | None) -> str:
            return "기재 없음" if value is None else ("허용" if value else "불가")

        return [
            f"모델: {self.name or '(이름 없음)'}" + (f", 제작자 {', '.join(self.authors)}" if self.authors else "") + f" (VRM {self.spec})",
            f"아바타 사용: {_PERMISSIONS.get(self.avatar_permission, '기재 없음')}",
            f"영리 사용: {_COMMERCIAL.get(self.commercial_usage, '기재 없음')}",
            f"크레딧 표기: {'기재 없음' if self.credit_required is None else ('필요' if self.credit_required else '불필요')}",
            f"개변: {_MODIFICATION.get(self.modification, '기재 없음')}, 재배포: {yes_no(self.redistribution)}",
            f"폭력 표현: {yes_no(self.violent)}, 성적 표현: {yes_no(self.sexual)}, 정치 및 종교: {yes_no(self.political)}, 반사회 및 혐오: {yes_no(self.antisocial)}",
        ] + ([f"라이선스: {self.license}"] if self.license else []) + ([f"추가 조건: {self.other_license_url}"] if self.other_license_url else [])


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
        issues.append(Issue("warning", "제작자 본인만 사용할 수 있는 모델입니다. 제작자가 아니면 사용할 수 없습니다."))
    elif meta.avatar_permission == "onlySeparatelyLicensedPerson":
        issues.append(Issue("warning", "별도 허락을 받은 사람만 사용할 수 있는 모델입니다. 허락 여부를 확인해야 합니다."))
    elif not meta.avatar_permission:
        issues.append(Issue("warning", "아바타 사용 허용 범위가 파일에 기재되어 있지 않습니다. 배포처의 약관을 확인해야 합니다."))
    if corporation and meta.commercial_usage in ("personalNonProfit", "personalProfit"):
        issues.append(Issue("error", f"법인이 사용할 수 없는 모델입니다 (허용 범위: {_COMMERCIAL[meta.commercial_usage]})."))
    elif monetized and meta.commercial_usage == "personalNonProfit":
        issues.append(Issue("error", "수익을 얻는 채널에서 사용할 수 없는 모델입니다 (허용 범위: 개인의 비영리 사용만)."))
    elif (monetized or corporation) and not meta.commercial_usage:
        issues.append(Issue("warning", "영리 사용 허용 여부가 파일에 기재되어 있지 않습니다. 배포처의 약관을 확인해야 합니다."))
    if meta.credit_required:
        credit = " / ".join(part for part in (meta.name, ", ".join(meta.authors)) if part)
        issues.append(Issue("warning", "크레딧 표기가 필요합니다" + (f": {credit}" if credit else ".")))
    if meta.other_license_url:
        issues.append(Issue("info", f"추가 조건 확인: {meta.other_license_url}"))
    if meta.spec == "0.x":
        issues.append(Issue("info", "VRM 0.x 메타는 영리 사용을 허용과 불가로만 구분합니다. 개인과 법인의 구분은 배포처의 약관에서 확인해야 합니다."))
    return issues
