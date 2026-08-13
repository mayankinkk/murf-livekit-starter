#!/bin/bash

# Start all services in background
if [ -f "/home/mayank/Documents/Murf AI/livekit-server" ]; then
  "/home/mayank/Documents/Murf AI/livekit-server" --dev > ../livekit.log 2>&1 &
  echo "Started local livekit-server"
else
  echo "Warning: livekit-server not found. Skipping local LiveKit startup and using your configured LIVEKIT_URL instead."
fi

(cd backend && uv run python src/agent.py dev > agent.log 2>&1) &
echo "Started backend agent"

(cd frontend && pnpm dev > frontend.log 2>&1) &
echo "Started frontend"

# Wait for all background jobs
wait
