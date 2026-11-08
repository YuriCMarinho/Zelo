import pytest

from app.agents.commercial import _format_commercial_response


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        (
            "Olá! Bem-vindo ao **Loft Moderno**! 🌿✨ Como posso ajudar? 😊🏡",
            "Olá! Bem-vindo ao Loft Moderno! 🌿 Como posso ajudar?",
        ),
        (
            "Use a rede PortoDigital_Tech. O acesso é __autônomo__ e *simples*.",
            "Use a rede PortoDigital_Tech. O acesso é autônomo e simples.",
        ),
        ("Olá! 👩🏽‍💻 Tudo bem? 🏡", "Olá! 👩🏽‍💻 Tudo bem?"),
        ("Como posso ajudar?", "Como posso ajudar?"),
    ],
)
def test_commercial_response_removes_emphasis_and_limits_emojis(
    content: str, expected: str
) -> None:
    assert _format_commercial_response(content) == expected
