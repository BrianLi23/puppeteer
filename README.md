# Puppeteer: an AI Runtime proof-of-Concept
This is a project written in 30 hours for the **Hack the North Hackathon**. (And later refactored and revamped for better UI and logic)
For more information and a demo video, check out our [Devpost submission](https://devpost.com/software/puppeteer-7429qv).

## Description
**Puppeteer** is a proof-of-concept _AI runtime_. When executing the program with an AI runtime, instead of running the entire program through the language's runtime (the Python interpreter in this demo), the AI runtime forwards some of the instructions that are of particular interest to the user to an AI agent for execution. The agent can monitor and override instructions by generating an output.

This allows the agent to:
  * Simulate the program in imaginary scenarios asked by the users.
  * Stop the program under complex conditions.
  * Report on specific events.
  * And so on ...

## Getting Started (UV Project)
For using Puppeteer in your project, first you should clone this project and install the dependencies using:
  ```bash
  uv sync
  ```
## Using the CLI to Add Probes
You can add the probes manually or by running the CLI targeted to your project and asking it to add probes. To run the CLI, use the following command:
```bash
uv run terminal.py -- --path path/to/target/code
```

## Running the AI Runtime in Your Code
After adding the probes, you must install the `puppeteer` library into your program's environment. The library is not available on PyPI, so you should install it locally using:
```bash
uv add --editable path/to/puppeteer
```
or
```bash
pip install -e path/to/puppeteer
  ```
Then, run the program normally. Using the CLI targeted to your program directory, you can then prompt the AI runtime.

## License
This project is licensed under the **Apache 2** license.
