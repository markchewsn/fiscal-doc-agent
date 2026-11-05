from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import RunnableLambda


class FakeChat(BaseChatModel):
    """Scripted chat model: canned turns, canned structured outputs; records bound tools and
    the messages of each turn."""

    turns: list[AIMessage]
    structured: list[dict] = []
    tools_per_turn: list[list[str]] = []
    seen: list[list] = []

    @property
    def _llm_type(self) -> str:
        return "fake-chat"

    def bind_tools(self, tools, **_):
        self.tools_per_turn.append([t.name if hasattr(t, "name") else t["name"] for t in tools])
        return self

    def _generate(self, messages, stop=None, run_manager=None, **_):
        self.seen.append(messages)
        return ChatResult(generations=[ChatGeneration(message=self.turns.pop(0))])

    def with_structured_output(self, schema, **_):
        return RunnableLambda(lambda _: schema.model_validate(self.structured.pop(0)))
