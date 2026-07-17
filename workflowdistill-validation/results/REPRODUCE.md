# Reproduce

The run did not lock a finalist, so this is a measurement replay, not a clean
finalist reproduction.

```bash
python3 tools/run_pomerium_boundary_gate.py
python3 tools/run_official_visible.py hosted
```

Untouched Bonsai launch (no adapter):

```bash
GGML_GDN_STATE_INPLACE=1 GGML_METAL_Q1_Q8_BP=1 \
  $HOME/projects/navilan/research/bonsai-reasearch/runs/M015-r4s4-ncb2-lto/build/bin/llama-server \
  -m $HOME/models/Bonsai-27B-Q1_0.gguf -ngl 99 -fa on \
  -ctk f16 -ctv f16 -b 512 -ub 64 -t 4 -c 16384 \
  --reasoning off --reasoning-budget 0 -np 1 -ctxcp 0 -cram 0 \
  --no-cache-idle-slots --no-cache-prompt --host 127.0.0.1 \
  --port 8081 --jinja
python3 tools/run_official_visible.py bonsai
```

The p42 experiment adds only:
`--lora $HOME/models/bonsai-heretic/Bonsai-27B-Heretic-p42-f16.gguf`
and runs `python3 tools/run_p42_selection.py`.
