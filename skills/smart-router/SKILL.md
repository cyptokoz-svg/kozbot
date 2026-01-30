# Smart Model Router (Skill)

## Description
This skill empowers the agent to act as a "Smart Router," dynamically switching its own underlying model based on the complexity of the user's request. This optimization ensures simple tasks are handled quickly (and cheaply) while complex tasks receive maximum reasoning power.

## Usage
The agent should continuously evaluate the current task complexity.

### Triggers
- **High Complexity Detected**: Coding, architecture design, complex debugging, creative writing, nuanced analysis.
  - **Action**: Switch to a **High-Reasoning Model** (e.g., `google/gemini-3-pro-preview`, `anthropic/claude-3-5-sonnet`, or `anthropic/claude-3-opus`).
- **Low Complexity Detected**: Casual chat, simple factual queries, summaries, list management.
  - **Action**: Switch to a **Fast/Efficiency Model** (e.g., `google/gemini-3-flash-preview` or `anthropic/claude-3-haiku`).

### How to Switch
Use the `session_status` tool with the `model` parameter.

```javascript
// Example: Upgrade to Pro for coding
session_status({ model: "google/gemini-3-pro-preview" });

// Example: Downgrade to Flash for chat
session_status({ model: "google/gemini-3-flash-preview" });
```

## Strategy: "The Triage"
1.  **Analyze**: Before diving into a large task, pause and ask: "Is my current model sufficient?"
2.  **Switch**: If no, announce the switch to the user ("Switching to high-performance mode for this task...") and call `session_status`.
3.  **Execute**: Proceed with the task.

## Configuration
- **Eco Mode (Default)**: `google/gemini-3-flash-preview`
- **Power Mode**: `google/gemini-3-pro-preview`
