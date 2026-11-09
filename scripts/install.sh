#!/usr/bin/env bash
set -euo pipefail
trap 'echo "::error::Please Behave installation failed at line $LINENO. Check the release tag, release assets and network access." >&2' ERR

if [[ ! "$PLEASE_VERSION" =~ ^v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$ ]]; then
  echo "::error::version must be an exact stable release tag, such as v1.2.3." >&2
  exit 1
fi
if [[ "$PLEASE_RUN" != true && "$PLEASE_RUN" != false ]]; then
  echo "::error::run must be true or false." >&2
  exit 1
fi
if [[ "$PLEASE_SUMMARY" != true && "$PLEASE_SUMMARY" != false ]]; then
  echo "::error::summary must be true or false." >&2
  exit 1
fi
if [[ "$RUNNER_OS" != Linux ]]; then
  echo "::error::The Please Behave Action supports GitHub-hosted Ubuntu 24.04 runners only." >&2
  exit 1
fi
case "$RUNNER_ARCH" in
  X64) target=x86_64-unknown-linux-gnu ;;
  ARM64) target=aarch64-unknown-linux-gnu ;;
  *) echo "::error::Unsupported Ubuntu runner architecture: $RUNNER_ARCH" >&2; exit 1 ;;
esac

work=$(mktemp -d "$RUNNER_TEMP/please-download.XXXXXX")
trap 'rm -rf "$work"' EXIT
name="please-$PLEASE_VERSION-$target"
archive="$name.tar.gz"
base="https://github.com/please-behave/cli/releases/download/$PLEASE_VERSION"
curl --fail --show-error --silent --location --retry 3 --connect-timeout 15 --max-time 120 "$base/$archive" -o "$work/$archive"
curl --fail --show-error --silent --location --retry 3 --connect-timeout 15 --max-time 120 "$base/SHA256SUMS" -o "$work/SHA256SUMS"
# Select exactly this archive; other platform downloads are not needed.
awk -v archive="$archive" '$2 == archive && $1 ~ /^[0-9a-f]+$/ && length($1) == 64 { print; count++ } END { if (count != 1) exit 1 }' "$work/SHA256SUMS" > "$work/selected-sum"
(cd "$work" && sha256sum --check selected-sum)
tar -xzf "$work/$archive" -C "$work" -- "$name/please"
if [[ ! -f "$work/$name/please" || -L "$work/$name/please" ]]; then
  echo "::error::Release archive has no regular please executable." >&2
  exit 1
fi
bin="$RUNNER_TEMP/please/bin"
mkdir -p "$bin"
install -m 755 "$work/$name/please" "$bin/please"
printf '%s\n' "$bin" >> "$GITHUB_PATH"
echo "Installed Please Behave $PLEASE_VERSION ($target)."
