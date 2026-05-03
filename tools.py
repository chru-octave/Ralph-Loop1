import subprocess
import os
from pathlib import Path

from subagents import haiku

WORKSPACE = Path(os.environ.get("RALPH_WORKSPACE", Path.cwd())).resolve()

SAFE_PREFIXES= (
# pure resd -- local
"ls", "cat", "dir" , "head", "tail", "pwd", "which", "type",
# system inspeaction
"uname",
# git reads"
"git status", "git diff", "git log", "git show", "git branch",
# test & lint 
"python -m pytest", "pytest", "uv run pytest", "ruff check", "mypy",
 
 )
MAX_TIMEOUT= 300
DEFAULT_TIMEOUT= 120
OUTPUT_HEAD=3000
OUTPUT_TAIL = 4000

TOOLS = [
    {
        "name": "read_file",
        "description": "Read the contents of a text file relative to the workspace root.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path relative to workspace root. No leading slash.",
                },
            },
            "required": ["path"],
        },
    },
    {
        "name": "write_haiku",
        "description": (
            "Convert provided text into haiku form (5-7-5 syllables). "
            "Use after you have gathered content and want a poetic summary. "
            "Pass the text to summarize in `content`."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "The text to summarize into haiku form.",
                },
                "count": {
                    "type": "integer",
                    "description": "How many haikus to produce. Default 1.",
                    "default": 1,
                },
            },
            "required": ["content"],
        },
    },

    {
        "name" : "write_file",
        "description":(
            "Write text to a file at the given path, relative to workspace root."
            "create the file if file doesn't exist, overwrite the file if file exists"
            "create the parent directory if needed"
            "This is a full file write"


        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["path", "content"],
        },
    },

    {
        "name" : "run_shell",
        "description":(
            "Run a shell command in the workspace root and return stdout,stderr, "
            "and exit code. Comands that would modify the system oitsode the "
            "workspace, network state, or package installations require approval."
            "outputs may be truncated for large results - "
            "if truncated a marker will appear showinh how many bytes were elided"

        ),
        "input_schema": {
            "type": "object",
            "properties":
            {
                "command": {
                    "type": "string",
                    "description": "Shell comamd to execute. Runs via /bin/sh -c"
                },
                "timeout": {
                    "type": "integer",
                    "description": "Timeout in seconds. default 120, max 300.",
                },
            },
            "required": ["command"]
        },
    }
]


def _is_safe(command : str) -> bool:
    return any(command.strip().startswith(p) for p in SAFE_PREFIXES)

def _truncate(text:str) -> str:
    if len(text) <= OUTPUT_HEAD + OUTPUT_TAIL:
        return text
    elided = len(text) - OUTPUT_HEAD - OUTPUT_TAIL
    return (
        text[:OUTPUT_HEAD]
        +f"\n\n[...{elided} bytes elided...]\n\n"
        + text[-OUTPUT_TAIL:]
    )

def _format_result(exit_code: int, stdout: str, stderr: str) -> str:
    return(
        f"exit: {exit_code}\n\n"
        f"----stdout ---\n{_truncate(stdout) or '(empty)'} \n\n"
        f"----stderr----\n{_truncate(stderr) or '(empty)'}) "
    )


def _run_shell(command: str, timeout: int = DEFAULT_TIMEOUT) -> str:
    timeout = min(max(1, timeout), MAX_TIMEOUT)

    if not _is_safe(command):
        print(f"\n[approval needed] {command}")
        response = input("approve? [y/N]: ").strip().lower()
        if response != "y":
            return f"Error: user denied approval for {command}"

    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=WORKSPACE,
            capture_output=True,
            timeout=timeout,
            env={**os.environ, "NO_COLOR": "1"},
        )
        return _format_result(
            result.returncode,
            result.stdout.decode("utf-8", errors="replace"),
            result.stderr.decode("utf-8", errors="replace"),
        )
    except subprocess.TimeoutExpired as e:
        partial = (e.stdout or b"").decode("utf-8", errors="replace")[-500:]
        return (
            f"Error: command exceeded {timeout}s timeout and was killed.\n"
            f"Partial stdout (last 500 bytes):\n{partial}"
        )
        


def resolve_in_workspace(rel: str) -> Path | str:
    """Return resolved Path inside workspace, or error string if it escapes."""
    target = (WORKSPACE / rel).resolve()
    if not target.is_relative_to(WORKSPACE):
        return f"ERROR: path {rel} escapes workspace"
    return target


def run_tool(name: str, tool_input: dict) -> str:
    if name == "read_file":
        rel = tool_input["path"]
        target = resolve_in_workspace(rel)
        if isinstance(target, str):
            return target

        if not target.exists():
            return f"Error: {rel} does not exist"
        if not target.is_file():
            return f"Error: {rel} is not a file"
        return target.read_text()

    if name == "write_haiku":
        return haiku.run(
            content=tool_input["content"],
            count=tool_input.get("count", 1),
        )

    if name == "write_file":
        rel = tool_input["path"]
        content = tool_input["content"]
        target = resolve_in_workspace(rel)
        if isinstance(target, str):
            return target

        if target.exists() and not target.is_file():
            return f"ERROR: {rel} exists and is not a regular file"

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
        return f"wrote {len(content)} bytes to {rel}"
    
    if name == "run_shell":
        return _run_shell(

            command = tool_input["command"],
            timeout=tool_input.get("timeout", DEFAULT_TIMEOUT),
        )

    return f"Error: unknown tool {name}"
