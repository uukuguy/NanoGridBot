#!/usr/bin/env bash

cd frontend && \
VITE_API_PROXY_TARGET=http://127.0.0.1:18081 VITE_WS_PROXY_TARGET=ws://127.0.0.1:18081 npm run dev
