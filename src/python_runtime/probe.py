import json
import os
import uuid
from typing import TypeVar, Generic, Any, Optional
import yaml
import datetime
import logging
from .runtime import Runtime

LOGGER = logging.getLogger(__name__)

T = TypeVar("T")

RESERVED_FIELDS = {
    "_obj",
    "_prompt",
    "_prefix",
    "_entry",
    "_runtime",
    "_stop_after",
    "_getattr_impl",
    "RESERVED_FIELDS",
}
class Probed(Generic[T]):
    def __init__(
        self,
        obj: T,
        prompt: str = "",
        prefix: str = "",
        stop_after: Optional[bool] = True,
        runtime: Optional[Runtime] = None,
        entry: Optional["Probed[Any]"] = None,
    ) -> None:
        self._obj = obj
        self._prompt = prompt
        self._prefix = prefix
        self._stop_after = stop_after
        if entry is not None:
            self._entry = entry
            self._runtime = entry._runtime
        else:
            self._prefix = f"{obj.__class__.__name__}_{str(uuid.uuid4())[:8]}"
            self._entry = self
            self._runtime = runtime
            runtime.register_probing(self)

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        data = json.dumps(
            {
                "function": self._prefix,
                "args": args,
                "kwargs": kwargs,
            },
            indent=2,
        )
        LOGGER.debug(f"DEBUG: Probed call data: {data}")
        should_be_interrupted, should_be_reported, should_be_stopped = (
            self._runtime.ask_model_decisions(self._entry, data)
        )
        LOGGER.debug(
            f"DEBUG: Model decisions - Interrupt: {should_be_interrupted}, Report: {should_be_reported}, Stop: {should_be_stopped}"
        )
        print(
            f"Model Decisions - Interrupt: {should_be_interrupted}, Report: {should_be_reported}, Stop: {should_be_stopped}")
        if should_be_reported:
            report_data = {
                "timestamp": datetime.datetime.now().isoformat(),
                "event_data": json.loads(data),
            }
            with open("report.md", "a") as f:
                f.write(yaml.dump(report_data) + "\n---\n")
        stop_after = self._resolve_stop_after()
        if should_be_stopped and not stop_after:
            import ipdb

            ipdb.set_trace()
        if should_be_interrupted:
            result_schema = self._obj.__doc__
            print("the schema is :", result_schema)
            result_example = "No example provided"
            try:
                result_example = self._obj(*args, **kwargs)
            except Exception as e:
                pass
            result = self._runtime.respond_event(
                self._entry, data, result_schema, result_example
            )
            if should_be_stopped and stop_after:
                import ipdb

                ipdb.set_trace()
            return result
        else:
            result = self._obj(*args, **kwargs)
            self._runtime.listen_event(self._entry, data, result)
            if should_be_stopped and stop_after:
                import ipdb

                ipdb.set_trace()
            return result

    def _resolve_stop_after(self) -> bool:
        if self._entry._stop_after is not None:
            return self._entry._stop_after
        return os.getenv("PROBE_STOP_AFTER", "").lower() in {"1", "true", "yes"}

    def _getattr_impl(self, name: str) -> "Probed[Any]":
        print(f"__getattr__ called for {name}")
        if name in RESERVED_FIELDS:
            return super().__getattribute__(name)

        attr = getattr(self._obj, name)
        return Probed(
            attr,
            prompt=self._prompt,
            prefix=f"{self._prefix}.{name}",
            stop_after=self._stop_after,
            entry=self._entry,
        )

    def __getattr__(self, name: str) -> "Probed[Any]":
        return self._getattr_impl(name)

    def __setattr__(self, name: str, value: Any) -> None:
        if name in RESERVED_FIELDS:
            super().__setattr__(name, value)
            return

        setattr(self._obj, name, value)

    def __getitem__(self, key: Any) -> Any:
        result = self._obj[key]
        return result

    def __setitem__(self, key: Any, value: Any) -> None:
        self._obj[key] = value

    def __len__(self) -> Any:
        return self._getattr_impl("__len__")()

    def __repr__(self) -> str:
        return f"<Probe wrapping {repr(self._obj)}>"

    def __str__(self) -> Any:
        return self._getattr_impl("__str__")()

    def __hash__(self) -> int:
        return hash(self._prefix)

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, Probed):
            return self._obj == other._obj
        return self._obj == other


def probe(value: T, prompt: str, runtime: Runtime) -> Probed[T]:
    return Probed(value, prompt, runtime=runtime)
