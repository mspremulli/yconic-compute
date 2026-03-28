import asyncio
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Awaitable
import structlog

from swarm.types.message import AgentMessage, MessagePriority

logger = structlog.get_logger()


@dataclass
class Subscription:
    id: str
    agent_id: str
    topics: set[str]
    handler: Callable[[AgentMessage], Awaitable[None]]

    async def handle(self, message: AgentMessage) -> None:
        await self.handler(message)


class MessageBus:
    def __init__(self):
        self._subscriptions: dict[str, Subscription] = {}
        self._topic_to_subs: dict[str, set[str]] = defaultdict(set)
        self._reply_futures: dict[str, asyncio.Future] = {}
        self._lock = asyncio.Lock()

    async def publish(self, message: AgentMessage) -> None:
        async with self._lock:
            if not message.id:
                message.id = str(uuid.uuid4())
            if not message.timestamp:
                message.timestamp = datetime.utcnow()

            logger.debug(
                "message_published",
                message_id=message.id,
                topic=message.topic,
                sender=message.sender,
                recipients=message.recipients,
            )

            if message.reply_to and message.reply_to in self._reply_futures:
                future = self._reply_futures.pop(message.reply_to)
                if not future.done():
                    future.set_result(message)
                return

            await self._deliver(message)

    async def _deliver(self, message: AgentMessage) -> None:
        target_subs = set()

        for sub_id, sub in self._subscriptions.items():
            if message.sender == sub.agent_id:
                continue
            if sub.topics.intersection({message.topic, "*"}):
                target_subs.add(sub_id)

        if message.recipients:
            target_subs = {
                sid for sid in target_subs
                if self._subscriptions[sid].agent_id in message.recipients
            }

        if message.priority >= MessagePriority.HIGH.value:
            await asyncio.gather(
                *(self._subscriptions[sid].handle(message) for sid in target_subs),
                return_exceptions=True,
            )
        else:
            for sid in target_subs:
                asyncio.create_task(self._safe_handle(sid, message))

    async def _safe_handle(self, sub_id: str, message: AgentMessage) -> None:
        try:
            sub = self._subscriptions[sub_id]
            await sub.handle(message)
        except Exception as e:
            logger.error(
                "message_handler_error",
                subscription_id=sub_id,
                error=str(e),
            )

    async def subscribe(
        self,
        agent_id: str,
        topics: list[str],
        handler: Callable[[AgentMessage], Awaitable[None]],
    ) -> str:
        sub_id = str(uuid.uuid4())
        subscription = Subscription(
            id=sub_id,
            agent_id=agent_id,
            topics=set(topics),
            handler=handler,
        )

        async with self._lock:
            self._subscriptions[sub_id] = subscription
            for topic in topics:
                self._topic_to_subs[topic].add(sub_id)

        logger.debug("subscription_created", subscription_id=sub_id, agent_id=agent_id, topics=topics)
        return sub_id

    async def unsubscribe(self, subscription_id: str) -> None:
        async with self._lock:
            if subscription_id in self._subscriptions:
                sub = self._subscriptions.pop(subscription_id)
                for topic in sub.topics:
                    self._topic_to_subs[topic].discard(subscription_id)
                logger.debug("subscription_removed", subscription_id=subscription_id)

    async def send_direct(
        self,
        sender: str,
        recipient: str,
        payload: dict[str, Any],
        correlation_id: str | None = None,
    ) -> AgentMessage:
        message = AgentMessage(
            id=str(uuid.uuid4()),
            sender=sender,
            topic="direct",
            payload=payload,
            recipients=[recipient],
            correlation_id=correlation_id or str(uuid.uuid4()),
        )

        await self.publish(message)
        return message

    async def request_reply(
        self,
        sender: str,
        recipient: str,
        payload: dict[str, Any],
        timeout_seconds: float = 30.0,
    ) -> AgentMessage:
        correlation_id = str(uuid.uuid4())

        future: asyncio.Future[AgentMessage] = asyncio.get_event_loop().create_future()

        async with self._lock:
            self._reply_futures[correlation_id] = future

        message = AgentMessage(
            id=str(uuid.uuid4()),
            sender=sender,
            topic="direct",
            payload=payload,
            recipients=[recipient],
            correlation_id=correlation_id,
            reply_to=correlation_id,
        )

        await self.publish(message)

        try:
            return await asyncio.wait_for(future, timeout=timeout_seconds)
        except asyncio.TimeoutError:
            async with self._lock:
                self._reply_futures.pop(correlation_id, None)
            raise TimeoutError(f"No reply from {recipient} within {timeout_seconds}s")

    async def broadcast(
        self,
        sender: str,
        topic: str,
        payload: dict[str, Any],
        exclude: list[str] | None = None,
        priority: int = MessagePriority.NORMAL.value,
    ) -> None:
        recipients = None
        if exclude:
            async with self._lock:
                recipients = [
                    sub.agent_id
                    for sub in self._subscriptions.values()
                    if sub.agent_id not in exclude
                ]

        message = AgentMessage(
            id=str(uuid.uuid4()),
            sender=sender,
            topic=topic,
            payload=payload,
            recipients=recipients,
            priority=priority,
        )

        await self.publish(message)

    def get_subscriptions(self, agent_id: str) -> list[str]:
        return [
            sub_id
            for sub_id, sub in self._subscriptions.items()
            if sub.agent_id == agent_id
        ]

    def get_topics(self, agent_id: str) -> set[str]:
        topics = set()
        for sub in self._subscriptions.values():
            if sub.agent_id == agent_id:
                topics.update(sub.topics)
        return topics
