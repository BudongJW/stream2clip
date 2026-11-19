"""VRM avatars: the terms of use in the file are read (1.0 and 0.x) and a planned use is checked against them."""

from __future__ import annotations

import json
import struct

import pytest

from stream2clip.cli import main
from stream2clip.vrm import VrmMeta, check_vrm, read_vrm_meta, vrm_meta_from_json

META_1 = {
    "name": "Kiri", "version": "1.0", "authors": ["studio", "artist"], "licenseUrl": "https://vrm.dev/licenses/1.0/",
    "avatarPermission": "everyone", "commercialUsage": "personalProfit", "creditNotation": "required", "allowRedistribution": False,
    "modification": "allowModification", "allowExcessivelyViolentUsage": False, "allowExcessivelySexualUsage": False,
    "allowPoliticalOrReligiousUsage": False, "allowAntisocialOrHateUsage": False, "otherLicenseUrl": "https://example.com/terms",
}
META_0 = {
    "title": "Old model", "author": "someone", "allowedUserName": "ExplicitlyLicensedPerson", "violentUssageName": "Disallow",
    "sexualUssageName": "Disallow", "commercialUssageName": "Allow", "licenseName": "CC_BY_NC", "otherPermissionUrl": "https://example.com/old",
}


def glb(document: dict, path) -> None:
    """A binary glTF holding ``document`` and an empty binary chunk, as a VRM file is laid out."""
    body = json.dumps(document).encode("utf-8")
    body += b" " * (-len(body) % 4)
    chunks = struct.pack("<II", len(body), 0x4E4F534A) + body + struct.pack("<II", 0, 0x004E4942)
    path.write_bytes(struct.pack("<III", 0x46546C67, 2, 12 + len(chunks)) + chunks)


def levels(issues) -> list[str]:
    return [issue.level for issue in issues]


def test_vrm_1_meta_is_read_from_the_file(tmp_path):
    path = tmp_path / "kiri.vrm"
    glb({"asset": {"version": "2.0"}, "extensions": {"VRMC_vrm": {"specVersion": "1.0", "meta": META_1}}}, path)
    meta = read_vrm_meta(path)
    assert meta == VrmMeta(
        spec="1.0", name="Kiri", authors=("studio", "artist"), avatar_permission="everyone", commercial_usage="personalProfit", credit_required=True,
        redistribution=False, modification="allowModification", violent=False, sexual=False, political=False, antisocial=False,
        license="https://vrm.dev/licenses/1.0/", other_license_url="https://example.com/terms",
    )
    text = " | ".join(meta.summary())
    assert "Kiri" in text and "studio, artist" in text and "VRM 1.0" in text and "개인의 영리 사용까지" in text and "크레딧 표기: 필요" in text


def test_vrm_0_meta_is_brought_to_the_same_terms():
    meta = vrm_meta_from_json({"extensions": {"VRM": {"meta": META_0}}})
    assert meta.spec == "0.x" and meta.name == "Old model" and meta.authors == ("someone",)
    assert meta.avatar_permission == "onlySeparatelyLicensedPerson"
    assert meta.commercial_usage == "personalNonProfit"  # "Allow", but the licence it names is non-commercial
    assert meta.credit_required is True and meta.redistribution is True and meta.modification == "allowModificationRedistribution"
    assert meta.violent is False and meta.sexual is False and meta.political is None
    assert meta.other_license_url == "https://example.com/old"

    free = vrm_meta_from_json({"extensions": {"VRM": {"meta": {"allowedUserName": "Everyone", "commercialUssageName": "Allow", "licenseName": "CC0"}}}})
    assert free.commercial_usage == "corporation" and free.credit_required is False and free.avatar_permission == "everyone"
    closed = vrm_meta_from_json({"extensions": {"VRM": {"meta": {"allowedUserName": "OnlyAuthor", "commercialUssageName": "Disallow", "licenseName": "Redistribution_Prohibited"}}}})
    assert closed.redistribution is False and closed.commercial_usage == "personalNonProfit" and closed.credit_required is None
    assert vrm_meta_from_json({"extensions": {"VRM": {"meta": {"licenseName": "CC_BY_ND"}}}}).modification == "prohibited"


def test_files_that_are_not_vrm_are_refused(tmp_path):
    plain = tmp_path / "model.glb"
    glb({"asset": {"version": "2.0"}}, plain)
    with pytest.raises(ValueError, match="no VRM meta"):
        read_vrm_meta(plain)
    other = tmp_path / "picture.vrm"
    other.write_bytes(bytes([0x89, 0x50, 0x4E, 0x47]) + b"0" * 32)
    with pytest.raises(ValueError, match="Not a VRM file"):
        read_vrm_meta(other)


def test_planned_use_is_checked_against_the_terms():
    profit = vrm_meta_from_json({"extensions": {"VRMC_vrm": {"meta": META_1}}})
    assert levels(check_vrm(profit)) == ["warning", "info"]  # credit due, further terms to read
    assert any("Kiri / studio, artist" in issue.message for issue in check_vrm(profit))
    assert "error" not in levels(check_vrm(profit, monetized=True))  # a person may earn money with it
    assert levels(check_vrm(profit, corporation=True))[0] == "error"  # a company may not

    hobby = vrm_meta_from_json({"extensions": {"VRMC_vrm": {"meta": {**META_1, "commercialUsage": "personalNonProfit", "creditNotation": "unnecessary", "otherLicenseUrl": ""}}}})
    assert check_vrm(hobby) == []
    assert levels(check_vrm(hobby, monetized=True)) == ["error"]

    author_only = vrm_meta_from_json({"extensions": {"VRMC_vrm": {"meta": {"avatarPermission": "onlyAuthor"}}}})
    found = check_vrm(author_only, monetized=True)
    assert levels(found) == ["warning", "warning"] and "제작자 본인만" in found[0].message and "영리 사용 허용 여부" in found[1].message
    assert levels(check_vrm(vrm_meta_from_json({"extensions": {"VRMC_vrm": {"meta": {}}}})))[0] == "warning"  # nothing stated: ask the seller

    old = vrm_meta_from_json({"extensions": {"VRM": {"meta": META_0}}})
    assert levels(check_vrm(old, monetized=True)) == ["warning", "error", "warning", "info", "info"]


def test_check_command_reads_a_model(tmp_path, capsys):
    path = tmp_path / "kiri.vrm"
    glb({"extensions": {"VRMC_vrm": {"meta": {**META_1, "commercialUsage": "personalNonProfit"}}}}, path)
    assert main(["check", "--vrm", str(path)]) == 0
    out = capsys.readouterr().out
    assert "모델: Kiri" in out and "영리 사용: 개인의 비영리 사용만" in out and "크레딧 표기가 필요합니다" in out
    assert main(["check", "--vrm", str(path), "--monetized"]) == 1
    assert "수익을 얻는 채널에서 사용할 수 없는 모델" in capsys.readouterr().out
    # together with the guideline check of a clip
    assert main(["check", "--vrm", str(path), "--source-url", "https://youtu.be/x", "--source-title", "t", "--agency", "generic"]) == 0
    assert main(["check"]) == 1
    assert "--vrm" in capsys.readouterr().err
