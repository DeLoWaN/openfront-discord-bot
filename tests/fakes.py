from dataclasses import dataclass, field
from typing import Dict, List, Optional

from src.openfront import OpenFrontClient, OpenFrontError


class FakeOpenFront:
    def __init__(self, player_data=None, sessions=None, should_fail=False):
        self.player_data = player_data or {}
        self.sessions = sessions or []
        self.should_fail = should_fail

    async def fetch_player(self, player_id: str):
        if self.should_fail:
            raise OpenFrontError("simulated failure")
        return self.player_data

    async def fetch_sessions(self, player_id: str):
        if self.should_fail:
            raise OpenFrontError("simulated failure")
        return list(self.sessions)

    async def last_session_username(self, player_id: str):
        return None

    # Reuse parsing helpers from the real client
    @staticmethod
    def session_end_time(session):
        return OpenFrontClient.session_end_time(session)

    @staticmethod
    def session_win(session):
        return OpenFrontClient.session_win(session)


@dataclass
class FakeRole:
    id: int
    name: str


@dataclass
class FakeMember:
    id: int
    roles: List[FakeRole]
    guild: "FakeGuild"
    display_name: str = ""
    added_roles: List[int] = field(default_factory=list)
    removed_roles: List[int] = field(default_factory=list)

    async def add_roles(self, *roles: FakeRole, reason: Optional[str] = None):
        for role in roles:
            if role not in self.roles:
                self.roles.append(role)
            self.added_roles.append(role.id)

    async def remove_roles(self, *roles: FakeRole, reason: Optional[str] = None):
        for role in roles:
            if role in self.roles:
                self.roles.remove(role)
            self.removed_roles.append(role.id)


@dataclass
class FakeGuild:
    id: int
    roles: List[FakeRole]
    members: Dict[int, FakeMember]
    name: str = "TestGuild"

    def get_role(self, role_id: int) -> Optional[FakeRole]:
        for role in self.roles:
            if role.id == role_id:
                return role
        return None

    def get_member(self, member_id: int) -> Optional[FakeMember]:
        return self.members.get(member_id)
