import json
import hashlib
import copy
from python_runtime.probe import Probed
from python_runtime.runtime import Runtime
from ai_runtime.prompts import (
    DECISION_HISTORY_TEMPLATE,
    INIT,
    LISTENING_HISTORY_TEMPLATE,
    RESPONDING_HISTORY_TEMPLATE,
    ASK_MODEL_DECISION,
    RESPOND_EVENT,
    LISTEN_EVENT,
)
import agent as agent


class AIRuntime(Runtime):
    def __init__(self, enable_cache=True):
        self.probed_objects: dict[Probed, str] = {}
        self.enable_cache = enable_cache
        self.response_cache: dict[str, any] = {} if enable_cache else None
        self.user_query_hash: str = ""  # Track query changes
        self.user_query_content: str = ""  # Cache query content

    def get_user_additional_query(self) -> str:
        try:
            with open("user_query.md", "r") as file:
                content = file.read()
                # Check if query changed (only if caching enabled)
                if self.enable_cache:
                    new_hash = hashlib.md5(content.encode()).hexdigest()
                    if new_hash != self.user_query_hash:
                        print(f"🔄 User query changed (old: {self.user_query_hash[:8] if self.user_query_hash else 'empty'}, new: {new_hash[:8]}), clearing cache (size: {len(self.response_cache)})...")
                        self.response_cache.clear()
                        self.user_query_hash = new_hash
                        self.user_query_content = content
                return content
        except FileNotFoundError:
            return ""

    def register_probing(self, probed: Probed) -> None:
        self.probed_objects[probed] = INIT.format(
            type=type(probed._obj).__name__,
            initial_state=str(probed._obj),
            user_instructions=probed._prompt,
        )

    def ask_model_decisions(
        self, probed: Probed, event_content: str
    ) -> tuple[bool, bool, bool]:
        history = self.probed_objects[probed]
        user_additional_query = self.get_user_additional_query()
        
        # This passes the json represeentation of the event that occured
        prompt = ASK_MODEL_DECISION.format(
            history=history,
            event_content=event_content,
            user_additional_query=user_additional_query,
        )
        output = json.loads(agent.llm_call(prompt))
        result = (
            output.get("should_interrupt", False),
            output.get("should_report", False),
            output.get("should_stop", False),
        )
        history += "\n" + DECISION_HISTORY_TEMPLATE.format(
            event_content=event_content,
            interrupted="interrupt" if result[0] else "not interrupt",
            reported="reported" if result[1] else "not reported",
            stopped="stopped" if result[2] else "not stopped",
        )
        self.probed_objects[probed] = history
        return result

    def listen_event(self, probed: Probed, event_content: str, result: str) -> None:
        history = self.probed_objects[probed]
        user_additional_query = self.get_user_additional_query()
        prompt = LISTEN_EVENT.format(
            history=history,
            event_content=event_content,
            result=result,
            user_additional_query=user_additional_query,
        )
        agent.llm_call(prompt)
        history += "\n" + LISTENING_HISTORY_TEMPLATE.format(
            result=result,
        )
        self.probed_objects[probed] = history

    def respond_event(
        self,
        probed: Probed,
        event_content: str,
        result_schema: str,
        result_example: str,
    ) -> str:
        # Get user query first - this checks if it changed and clears cache if needed
        user_additional_query = self.get_user_additional_query()
        
        # Only use cache if enabled
        if self.enable_cache:
            # Create cache key from event + schema (query checked above)
            cache_key = hashlib.md5(
                f"{event_content}|{result_schema}".encode()
            ).hexdigest()
            
            print(f"📦 Cache status: {len(self.response_cache)} items, checking key {cache_key[:8]}...")
            
            # Check cache - skip LLM call if hit
            if cache_key in self.response_cache:
                print(f"🎯 Cache HIT for {cache_key[:8]}... Skipping LLM call")
                # Return deep copy to prevent modifications from affecting cache
                return copy.deepcopy(self.response_cache[cache_key])
            
        
        history = self.probed_objects[probed]
        print("the schema is :", result_schema)
        prompt = RESPOND_EVENT.format(
            history=history,
            event_content=event_content,
            response_format=result_schema,
            response_example=result_example,
            user_additional_query=user_additional_query,
        )
        model_output = agent.llm_call(prompt)
        output = json.loads(model_output)

        history += "\n" + RESPONDING_HISTORY_TEMPLATE.format(
            response=output,
        )
        self.probed_objects[probed] = history
        
        # Store in cache if enabled
        if self.enable_cache:
            self.response_cache[cache_key] = output
            print(f"💾 Stored in cache, new size: {len(self.response_cache)}")
        return output
