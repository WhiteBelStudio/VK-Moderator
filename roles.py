from enum import Enum


class Role(str, Enum):
    MANIAC = "maniac"
    SHERIFF = "sheriff"
    DOCTOR = "doctor"
    CIVILIAN = "civilian"

    @property
    def title(self) -> str:
        titles = {
            Role.MANIAC: "🔪 Маньяк",
            Role.SHERIFF: "🕵️ Шериф",
            Role.DOCTOR: "🩺 Доктор",
            Role.CIVILIAN: "👤 Мирный",
        }

        return titles[self]

    @property
    def team(self) -> str:
        if self == Role.MANIAC:
            return "maniac"

        return "civilians"