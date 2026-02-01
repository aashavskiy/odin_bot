from types import SimpleNamespace

from app.access import is_mention, is_reply_to_bot


def test_is_mention_case_insensitive():
    assert is_mention("Hi @MyBot", "mybot") is True


def test_is_mention_missing_text_or_username():
    assert is_mention(None, "mybot") is False
    assert is_mention("hello", None) is False


def test_is_reply_to_bot_requires_username_match():
    message = SimpleNamespace(
        reply_to_message=SimpleNamespace(
            from_user=SimpleNamespace(id=1, username="mybot")
        )
    )
    assert is_reply_to_bot(message, "mybot") is True
    assert is_reply_to_bot(message, "otherbot") is False


def test_is_reply_to_bot_no_reply_or_username():
    message = SimpleNamespace(reply_to_message=None)
    assert is_reply_to_bot(message, "mybot") is False
