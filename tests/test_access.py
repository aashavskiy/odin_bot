from types import SimpleNamespace

from app.access import should_leave_chat, should_respond


def make_message(
    *,
    sender_id: int,
    chat_type: str,
    text: str | None,
    bot_username: str | None,
    reply: bool = False,
    caption: str | None = None,
):
    reply_to = None
    if reply:
        reply_to = SimpleNamespace(from_user=SimpleNamespace(id=999, username=bot_username))
    return SimpleNamespace(
        from_user=SimpleNamespace(id=sender_id, username="user"),
        chat=SimpleNamespace(id=1, type=chat_type),
        text=text,
        caption=caption,
        reply_to_message=reply_to,
    )


def test_should_respond_private_admin():
    message = make_message(sender_id=100013433, chat_type="private", text="hi", bot_username="mybot")
    assert should_respond(message, "mybot", 100013433) is True


def test_should_respond_private_non_admin():
    message = make_message(sender_id=1, chat_type="private", text="hi", bot_username="mybot")
    assert should_respond(message, "mybot", 100013433) is False


def test_should_respond_group_admin_without_mention():
    message = make_message(sender_id=100013433, chat_type="group", text="hello", bot_username="mybot")
    assert should_respond(message, "mybot", 100013433) is False


def test_should_respond_group_admin_with_mention():
    message = make_message(sender_id=100013433, chat_type="group", text="@mybot hello", bot_username="mybot")
    assert should_respond(message, "mybot", 100013433) is True


def test_should_respond_group_admin_with_reply():
    message = make_message(
        sender_id=100013433,
        chat_type="supergroup",
        text="reply",
        bot_username="mybot",
        reply=True,
    )
    assert should_respond(message, "mybot", 100013433) is True


def test_should_respond_group_admin_with_caption_mention():
    message = make_message(
        sender_id=100013433,
        chat_type="group",
        text=None,
        caption="@mybot hello",
        bot_username="mybot",
    )
    assert should_respond(message, "mybot", 100013433) is True


def test_should_leave_chat_for_non_admin():
    event = SimpleNamespace(from_user=SimpleNamespace(id=55), chat=SimpleNamespace(id=1, type="group"))
    assert should_leave_chat(event, 100013433) is True


def test_should_leave_chat_for_admin():
    event = SimpleNamespace(from_user=SimpleNamespace(id=100013433), chat=SimpleNamespace(id=1, type="group"))
    assert should_leave_chat(event, 100013433) is False
