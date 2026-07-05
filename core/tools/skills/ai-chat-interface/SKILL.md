---
kenbun:
  mode: interactive
  fidelity: high
  tech_stack: [react, tailwindcss, framer-motion, react-markdown]
  discovery_required: true
---

# ai-chat-interface

Generates a modern conversational AI interface or "Copilot" sidebar.

## Execution Directives

1. **Layout & UX**: Handle complex chat UX requirements such as streaming text simulations, markdown rendering, code block syntax highlighting, and quick-action suggestion chips.
2. **Components**:
   - Main Chat Area
   - Input Box with submit and attachment buttons
   - Suggestion Chips
   - Markdown and Code Block renderers for messages
3. **Animations**: Smoothly animate new messages appearing and typing indicators using framer-motion.
4. **Output Format**: The skill MUST produce a single, self-contained HTML `<artifact>` block, properly sandboxed per protocol.
5. **Responsiveness**: Ensure the interface is responsive within the constraints of the Visual Observatory's device frames.
