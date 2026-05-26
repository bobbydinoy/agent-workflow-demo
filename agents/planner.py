"""Planner agent for creating workflow task sequences."""

from __future__ import annotations

import logging
from typing import Iterable

logger = logging.getLogger(__name__)


class PlannerAgent:
    """Create an extensible plan of workflow tasks from a user goal."""

    def __init__(self) -> None:
        self._base_plan: list[str] = ["research", "analyze", "review"]
        self._task_map: dict[str, list[str]] = {
            "compliance": ["compliance_check"],
            "approval": ["human_approval"],
        }
        self._registered_tasks: set[str] = set(self._base_plan)
        for task_list in self._task_map.values():
            self._registered_tasks.update(task_list)

    def register_task(self, task_name: str) -> None:
        """Register future task names so they can appear in generated plans."""
        logger.info("Registering planner task: %s", task_name)
        self._registered_tasks.add(task_name)

    def register_goal_mapping(self, keyword: str, tasks: Iterable[str]) -> None:
        """Map a goal keyword to additional tasks for future extensibility."""
        self._task_map[keyword.lower()] = [task for task in tasks]

    def create_plan(self, user_goal: str) -> list[str]:
        """Build a task sequence that can expand as the system grows."""
        logger.info("Creating plan for goal: %s", user_goal)
        normalized_goal = user_goal.lower().strip()

        plan = list(self._base_plan)
        for keyword, mapped_tasks in self._task_map.items():
            if keyword in normalized_goal:
                for task_name in mapped_tasks:
                    if task_name in self._registered_tasks and task_name not in plan:
                        plan.append(task_name)

        logger.info("Plan created: %s", plan)
        return plan
