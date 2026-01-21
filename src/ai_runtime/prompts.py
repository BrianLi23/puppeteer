INIT = """
You are in control of an object in a Python program.
The object:
- Has type {type}
- Has initial state: {initial_state}

Your task is to monitor the object's interactions and:
- Decide whether you want to interrupt the operation or not.
    - If you decided to interrupt it:
        - The operation is not executed on the underlying object.
        - And you have to provide a response that will be returned instead of the actual operation result.
        - You will be informed of how the response should be formatted.
    - If you decided not to interrupt it:
        - The operation is executed on the underlying object.
        - And you will be informed of the result of the operation.

The user asks you to:
{user_instructions}

Examples for stopping:
- Should set stop when the object's current state matches the desired outcome of the user instructions
- This includes object's content, length, etc.
"""

ASK_MODEL_DECISION = """
What happened so far with this object:
{history}

User additional query (if any):
{user_additional_query}

An event is happening that is a method/function call on the object. The event is:
{event_content}
Do you want to interrupt this operation? 
Do you think this operation should be reported back to the developer?
Should we stop the program before this operation happens?
Only stop when the object's current state includes a basketball team; if unsure, do not stop.
The answer json schema is:
{{
    "should_interrupt": bool,
    "should_report": bool,
    "should_stop": bool
}}
"""

DECISION_HISTORY_TEMPLATE = """
This event was happening:
{event_content}
You decided to {interrupted} the operation.
Also the operation was {reported} to the developer.
This program {stopped} before this operation happened.
"""

RESPOND_EVENT = """
What happened so far with this object:
{history}

User additional query (if any):
{user_additional_query}

You decided to interrupt the operation. The event is:
{event_content}
The output response should be in the following json schema:
{response_format}
An example of what the response should look like is:
{response_example}
Your respond should be just a valid json object that conforms to the schema above and nothing else.
"""

RESPONDING_HISTORY_TEMPLATE = """
The response you provided was:
{response}
"""

LISTEN_EVENT = """
What happened so far with this object:
{history}

User additional query (if any):
{user_additional_query}

You decided NOT to interrupt the operation. The event is:
{event_content}
The result of the operation is:
{result}
Please acknowledge the result and update your understanding of the object's state.
"""

LISTENING_HISTORY_TEMPLATE = """
The result of the event was:
{result}
"""
