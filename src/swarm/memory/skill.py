import uuid
from dataclasses import dataclass, field
from datetime import datetime
import structlog

from swarm.db.connection import Database

logger = structlog.get_logger()


@dataclass
class Skill:
    id: str
    skill_name: str
    description: str | None = None
    prompt_template: str = ""
    success_rate: float = 0.0
    use_count: int = 0
    last_used: datetime | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)


class SkillMemory:
    def __init__(
        self,
        db: Database,
        success_rate_weight: float = 0.7,
        min_use_count: int = 3,
        decay_factor: float = 0.95,
    ):
        self.db = db
        self.success_rate_weight = success_rate_weight
        self.min_use_count = min_use_count
        self.decay_factor = decay_factor

    async def store(self, skill: Skill) -> str:
        if not skill.id:
            skill.id = str(uuid.uuid4())

        await self.db.execute(
            """INSERT OR REPLACE INTO skills 
               (id, skill_name, description, prompt_template, success_rate, use_count, last_used, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                skill.id,
                skill.skill_name,
                skill.description,
                skill.prompt_template,
                skill.success_rate,
                skill.use_count,
                skill.last_used.isoformat() if skill.last_used else None,
                skill.created_at.isoformat(),
            ),
        )

        logger.debug("skill_stored", skill_name=skill.skill_name)
        return skill.id

    async def retrieve(
        self,
        skill_name: str | None = None,
        min_success_rate: float = 0.5,
        limit: int = 20,
    ) -> list[Skill]:
        query = "SELECT * FROM skills WHERE 1=1"
        params = []

        if skill_name:
            query += " AND skill_name = ?"
            params.append(skill_name)

        query += " AND success_rate >= ? AND use_count >= ?"
        params.extend([min_success_rate, self.min_use_count])

        query += " ORDER BY success_rate DESC, use_count DESC LIMIT ?"
        params.append(limit)

        rows = await self.db.fetch_all(query, tuple(params))
        return [
            Skill(
                id=row["id"],
                skill_name=row["skill_name"],
                description=row["description"],
                prompt_template=row["prompt_template"],
                success_rate=row["success_rate"],
                use_count=row["use_count"],
                last_used=datetime.fromisoformat(row["last_used"]) if row["last_used"] else None,
                created_at=datetime.fromisoformat(row["created_at"]),
            )
            for row in rows
        ]

    async def update_success(
        self, skill_name: str, success: bool, update_template: str | None = None
    ) -> None:
        skill = await self.retrieve(skill_name=skill_name, min_success_rate=0.0, limit=1)
        if not skill:
            return

        s = skill[0]
        new_rate = (
            s.success_rate * self.decay_factor
            + (1.0 if success else 0.0) * (1 - self.decay_factor)
        )
        new_count = s.use_count + 1

        await self.db.execute(
            """UPDATE skills 
               SET success_rate = ?, use_count = ?, last_used = ?,
                   prompt_template = COALESCE(?, prompt_template)
               WHERE skill_name = ?""",
            (
                new_rate,
                new_count,
                datetime.utcnow().isoformat(),
                update_template,
                skill_name,
            ),
        )

        logger.debug("skill_updated", skill_name=skill_name, new_rate=new_rate)
