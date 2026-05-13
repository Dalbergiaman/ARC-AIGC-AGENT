from langchain_core.messages import AIMessage, HumanMessage

from agent.graph import has_explicit_generation_intent, resolve_generation_gate, route_after_evaluate


def test_generation_intent_requires_latest_user_message() -> None:
    messages = [
        HumanMessage(content="请生成图片"),
        AIMessage(content="好的"),
        HumanMessage(content="现代极简别墅，玻璃幕墙，黄昏光线，人视角"),
    ]

    assert has_explicit_generation_intent(messages) is False


def test_generation_intent_accepts_chinese_commands() -> None:
    assert has_explicit_generation_intent([HumanMessage(content="开始生成图片")]) is True
    assert has_explicit_generation_intent([HumanMessage(content="帮我出一张")]) is True
    assert has_explicit_generation_intent([HumanMessage(content="请渲染一下")]) is True


def test_generation_intent_accepts_english_commands() -> None:
    assert has_explicit_generation_intent([HumanMessage(content="generate an image")]) is True
    assert has_explicit_generation_intent([HumanMessage(content="render this design")]) is True
    assert has_explicit_generation_intent([HumanMessage(content="create image")]) is True


def test_generation_intent_negative_phrases_block_generation() -> None:
    assert has_explicit_generation_intent([HumanMessage(content="先不生成，继续调整材质")]) is False
    assert has_explicit_generation_intent([HumanMessage(content="不要出图，只讨论方案")]) is False
    assert has_explicit_generation_intent([HumanMessage(content="do not generate yet")]) is False


def test_generation_intent_ignores_image_send_context() -> None:
    assert has_explicit_generation_intent([
        HumanMessage(content="我发送了一张结构底图，请分析这张底图后续可以怎样优化。")
    ]) is False
    assert has_explicit_generation_intent([
        HumanMessage(content="我发送了一张图生图结构底图。底图说明：后面要生成高级效果图。请分析这张底图。")
    ]) is False
    assert has_explicit_generation_intent([
        HumanMessage(content="我发送了一张参考图，主要参考方向是：色彩。请分析如何用于后续生成。")
    ]) is False


def test_generation_intent_ignores_workspace_prompt_context() -> None:
    message = HumanMessage(content="继续调整立面材质\n[用户草稿 prompt: generate modern villa rendering]")

    assert has_explicit_generation_intent([message]) is False


def test_generation_gate_overrides_llm_generating_without_explicit_intent() -> None:
    ready, phase = resolve_generation_gate(
        llm_phase="generating",
        explicit_generation_intent=False,
    )

    assert ready is False
    assert phase == "collecting"


def test_generation_gate_allows_generation_with_explicit_intent() -> None:
    ready, phase = resolve_generation_gate(
        llm_phase="collecting",
        explicit_generation_intent=True,
    )

    assert ready is True
    assert phase == "generating"


def test_route_after_evaluate_does_not_retry_marginal_score_without_fatal_issue() -> None:
    assert route_after_evaluate({
        "retry_count": 0,
        "last_evaluation": {
            "score": 0.76,
            "fatal_issues": [],
        },
    }) == "__end__"


def test_route_after_evaluate_retries_fatal_issue_even_if_score_is_marginal() -> None:
    assert route_after_evaluate({
        "retry_count": 0,
        "last_evaluation": {
            "score": 0.76,
            "fatal_issues": ["透视明显错误"],
        },
    }) == "refine_prompt"


def test_route_after_evaluate_retries_low_score() -> None:
    assert route_after_evaluate({
        "retry_count": 0,
        "last_evaluation": {
            "score": 0.68,
            "fatal_issues": [],
        },
    }) == "refine_prompt"
