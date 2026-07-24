#!/bin/bash

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "Удаляем мусор..."

sudo rm -rf "$DIR/transcripts/"* "$DIR/results/"*

