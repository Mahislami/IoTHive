#!/bin/sh
set -eu

if [ "$#" -eq 0 ]; then
  echo "wait-for-files: missing arguments" >&2
  exit 1
fi

while [ "$#" -gt 0 ]; do
  case "$1" in
    --)
      shift
      if [ "$#" -eq 0 ]; then
        echo "wait-for-files: missing command after --" >&2
        exit 1
      fi
      exec "$@"
      ;;
    *)
      file="$1"
      shift
      until [ -f "$file" ]; do
        echo "Waiting for $file ..."
        sleep 1
      done
      ;;
  esac
done

echo "wait-for-files: missing -- separator" >&2
exit 1
