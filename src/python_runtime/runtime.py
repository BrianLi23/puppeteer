from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .probe import Probed 

class Runtime:
    def register_probing(self, probed: "Probed"):
        pass

    # Called when an event is listened to
    def listen_event(self, probed: "Probed", event_content: str, result: str) -> None:
        pass
    
    # Deciding whether to interrupt, report, or stop
    def ask_model_decisions(
        self, probed: "Probed", event_content: str
    ) -> tuple[bool, bool, bool]:
        pass

    # Responds to an interrupted event
    def respond_event(
        self,
        probed: "Probed",
        event_content: str,
        result_schema: str,
        result_example: str,
    ) -> str:
        pass