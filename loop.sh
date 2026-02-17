#!/usr/bin/env bash
export PATH="$HOME/.npm-global/bin:$HOME/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
cd ~/work/katala
while true; do
  claude -p "$(cat CLAUDE.md)" --allowedTools "Read,Write,Edit,Bash,Glob,Grep" 2>&1 | tee -a /tmp/katala_loop.log
  sleep 2
done
