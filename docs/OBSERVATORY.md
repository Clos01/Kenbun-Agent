# 🌌 The Observatory (GalaxyMap)

The **Observatory** is Kenbun's Next.js-based telemetry dashboard. It visualizes the current architectural layout of the agent swarm and the codebase as a dynamic, interactive "Galaxy Map".

## 🚀 Key Features

### 1. The Galaxy Map (Node Visualization)
The core of the Observatory is the `<GalaxyMap />` component (`dashboard/src/components/GalaxyMap.tsx`). It renders project files, daemons, and system layers as individual nodes in a 2D space.
- **Collision-Free Labels**: The map employs a collision-detection algorithm to ensure node labels never overlap, maintaining the Heritage minimalist aesthetic.
- **Pulsing Node Rings**: When a node is actively being processed by the Orchestrator, it visually "pulses", providing real-time telemetry on system focus.
- **Hover Card Telemetry**: Hovering over a node fetches and displays live telemetry data, including file size, last modified time, and system ownership.

### 2. Active Orchestration Jobs
The Observatory is directly hooked into the `orchestrator.py` layer. 
- You can select any node (e.g. a Python tool script) and click **"Audit Code"** or **"Autofix Bugs"**.
- This dispatches a live HTTP POST request to the backend Orchestrator.
- The UI immediately tracks the job status (`Running`, `Success`, `Error`), rendering a status suffix directly on the node label.

### 3. Interactive SVE Inspector
The **Sovereign Verification Engine (SVE)** Inspector is embedded in the dashboard (`dashboard/src/components/galaxy-map/InspectorPanel.tsx`).
- It allows you to trigger deep AST and logic reviews on any node.
- It displays the results of the `sve_pulse.py` daemon directly in the browser, showing exactly where architectural drift has occurred.

## 🎨 Design Philosophy
The Observatory strictly adheres to the **Heritage Design System** defined in `DESIGN.md`.
- **Colors**: Limestone and Boston Clay palettes.
- **Typography**: Inter / Space Grotesk.
- **Interaction**: Micro-animations powered by Framer Motion, ensuring interactions feel weighty but responsive.

## 🛠️ Architecture
- **Framework**: Next.js 16 (App Router)
- **Styling**: Tailwind CSS with custom Heritage tokens.
- **State Management**: React Context & Hooks (`activeJobs`, `hovered`, `transform`).
- **Real-Time Data**: Polling intervals that hook directly into the Kenbun API (`/orchestrate`, `/status`).
