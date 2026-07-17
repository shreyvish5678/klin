# 60-second demo script

## Opening

“Work Distill answers one question: can a cheaper local model replace a real
agent without changing the agent around it?”

Point to the latest-result strip:

“The newest report says a supervised-fine-tuned LoRA candidate reached 9/9 at
20 seconds. Work Distill preserves that update immediately while marking the
artifact verification that is still required.”

## Overview

1. Select `discord-agent`.
2. Click **Replay at 10×**.
3. “This is a sealed 22-event replay. Prompts, tools, fixtures, evaluator, and
   permissions stay fixed; only the model boundary changes.”
4. Let the three model paths stream.
5. “The system does not manufacture a winner. Hosted reached 4/9, untouched
   Bonsai 1/9, and p42 0/9, so rollback stayed active.”

## Technical

1. Open **Technical**.
2. “The DAG makes the invariant obvious: node 02 is swappable; authorization,
   receipts, Discord tools, and evaluation are locked.”
3. Point to the method queue.
4. “These are next experiments, not retroactive claims. A fresh result becomes
   measured only after its bundle and hashes verify.”
5. Expand **Technical details** to show events, visible checks, and metrics.

## Close

“The product is the evidence pipeline: safe model replacement that knows when
not to cut over.”
