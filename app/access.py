from __future__ import annotations

from typing import Protocol


class UserLike(Protocol):
    id: int
    username: str | None


class ChatLike(Protocol):
    id: int
    type: str


class MessageLike(Protocol):
    from_user: UserLike | None
    chat: ChatLike
    text: str | None
    reply_to_message: "MessageLike | None"


class ChatMemberUpdatedLike(Protocol):
    from_user: UserLike | None
    chat: ChatLike


def is_admin(user_id: int | None, admin_id: int) -> bool:
    return user_id == admin_id


def is_group_chat(chat_type: str) -> bool:
    return chat_type in {"group", "supergroup"}


def is_mention(text: str | None, bot_username: str | None) -> bool:
    if not text or not bot_username:
        return False
    return f"@{bot_username.lower()}" in text.lower()


def is_reply_to_bot(message: MessageLike, bot_username: str | None) -> bool:
    if not message.reply_to_message or not bot_username:
        return False
    reply_user = message.reply_to_message.from_user
    return reply_user is not None and reply_user.username == bot_username


def should_respond(message: MessageLike, bot_username: str | None, admin_id: int) -> bool:
    sender_id = message.from_user.id if message.from_user else None
    if not is_admin(sender_id, admin_id):
        return False

    if is_group_chat(message.chat.type):
        return is_mention(message.text, bot_username) or is_reply_to_bot(
            message, bot_username
        )

    return True


def should_leave_chat(event: ChatMemberUpdatedLike, admin_id: int) -> bool:
    actor_id = event.from_user.id if event.from_user else None
    return not is_admin(actor_id, admin_id)
