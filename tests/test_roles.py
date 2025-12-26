import asyncio
from types import SimpleNamespace

from src.bot import apply_roles
from tests.fakes import FakeGuild, FakeMember, FakeRole


def make_threshold(wins: int, role_id: int):
    return SimpleNamespace(wins=wins, role_id=role_id)


def test_apply_roles_assigns_highest_and_removes_lower():
    guild = FakeGuild(
        id=1,
        roles=[FakeRole(1, "low"), FakeRole(2, "high")],
        members={},
    )
    member = FakeMember(id=10, roles=[guild.roles[0]], guild=guild)
    guild.members[member.id] = member
    thresholds = [make_threshold(5, 1), make_threshold(10, 2)]

    target = asyncio.run(apply_roles(member, thresholds, win_count=12))

    assert target == 2
    assert member.added_roles == [2]
    assert member.removed_roles == [1]
    assert {r.id for r in member.roles} == {2}


def test_apply_roles_clears_threshold_roles_when_below_minimum():
    guild = FakeGuild(
        id=1,
        roles=[FakeRole(1, "low"), FakeRole(2, "high")],
        members={},
    )
    member = FakeMember(id=10, roles=list(guild.roles), guild=guild)
    guild.members[member.id] = member
    thresholds = [make_threshold(5, 1), make_threshold(10, 2)]

    target = asyncio.run(apply_roles(member, thresholds, win_count=0))

    assert target is None
    assert set(member.removed_roles) == {1, 2}
    assert member.added_roles == []
    assert {r.id for r in member.roles} == set()


def test_apply_roles_is_idempotent_when_role_already_correct():
    guild = FakeGuild(
        id=1,
        roles=[FakeRole(1, "low"), FakeRole(2, "high")],
        members={},
    )
    member = FakeMember(id=10, roles=[guild.roles[1]], guild=guild)
    guild.members[member.id] = member
    thresholds = [make_threshold(5, 1), make_threshold(10, 2)]

    target = asyncio.run(apply_roles(member, thresholds, win_count=12))

    assert target == 2
    assert member.added_roles == []
    assert member.removed_roles == []
    assert {r.id for r in member.roles} == {2}
