"""Event-2 叙事生成结果 Schema（Phase C-Event-2）。

EventNarrative 是事件级叙事（标题 + 描述）的领域对象，
由 DeepSeekProvider.generate_event_narrative 产出，
经 narrative 编排器校验后写回 Event.title / Event.description。

约束（与用户 Phase C 范围一致）：
- 只承载叙事文本，不引入 DB 新列；复用 Event.title / Event.description。
- title / description 必须非空；长度上限由编排器强制截断（见 narrative.py）。
- 不回退到裸 dict，保持类型约束。
"""
from pydantic import BaseModel, Field


class EventNarrative(BaseModel):
    """单个事件的生成式叙事（标题 + 描述）。

    允许空字符串：模型可能返回空，由 narrative 编排器在生成时显式校验
    （if not title or not desc -> raise -> 降级规则叙事）。
    """

    title: str = Field(..., description="事件标题")
    description: str = Field(..., description="事件描述")

    model_config = {"extra": "forbid"}
