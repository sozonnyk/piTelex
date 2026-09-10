#!/usr/bin/env bash
set -euo pipefail

usage() {
    cat <<'EOF'
Usage: setup-web-port-forward.sh [public-port] [target-port]

Install a persistent nftables redirect for the piTelex web module.
Defaults redirect inbound IPv4 TCP port 80 to local port 8080:

    sudo ./setup-web-port-forward.sh
    sudo ./setup-web-port-forward.sh 80 8080

The script writes a dedicated nftables include file and enables
nftables.service. It backs up /etc/nftables.conf before editing it.
EOF
}

die() {
    echo "error: $*" >&2
    exit 1
}

is_port() {
    case "$1" in
        ''|*[!0-9]*)
            return 1
            ;;
    esac
    [ "$1" -ge 1 ] && [ "$1" -le 65535 ]
}

case "${1:-}" in
    -h|--help)
        usage
        exit 0
        ;;
esac

[ "$#" -le 2 ] || {
    usage >&2
    exit 1
}

PUBLIC_PORT=${1:-80}
TARGET_PORT=${2:-8080}
NFTABLES_CONF=${NFTABLES_CONF:-/etc/nftables.conf}
NFTABLES_RULE_DIR=${NFTABLES_RULE_DIR:-/etc/nftables.d}
NFTABLES_RULE_FILE=${NFTABLES_RULE_FILE:-$NFTABLES_RULE_DIR/pitelex-web-redirect.nft}

is_port "$PUBLIC_PORT" || die "invalid public port: $PUBLIC_PORT"
is_port "$TARGET_PORT" || die "invalid target port: $TARGET_PORT"

if [ "$(id -u)" -ne 0 ]; then
    command -v sudo >/dev/null 2>&1 || die "run as root or install sudo"
    exec sudo "$0" "$@"
fi

NFT=$(command -v nft || true)
[ -n "$NFT" ] || die "nft command not found; install the nftables package"

redirect_pattern="tcp[[:space:]]+dport[[:space:]]+$PUBLIC_PORT([[:space:]]+counter)?[[:space:]]+redirect[[:space:]]+to[[:space:]]+:$TARGET_PORT"
conflicting_redirect_pattern="tcp[[:space:]]+dport[[:space:]]+$PUBLIC_PORT.*redirect[[:space:]]+to[[:space:]]+:[0-9]+"

backup_conf=
tmp_rule=
redirect_already_present=false

cleanup() {
    [ -z "${tmp_rule:-}" ] || rm -f "$tmp_rule"
}
trap cleanup EXIT

install -d -m 0755 "$NFTABLES_RULE_DIR"
tmp_rule=$(mktemp "$NFTABLES_RULE_FILE.tmp.XXXXXX")

cat > "$tmp_rule" <<EOF
# Managed by piTelex utils/systemd/setup-web-port-forward.sh
# Redirect inbound HTTP clients to the piTelex web module.
table ip pitelex_web_redirect {
    chain prerouting {
        type nat hook prerouting priority dstnat; policy accept;
        tcp dport $PUBLIC_PORT counter redirect to :$TARGET_PORT
    }
}
EOF

install -m 0644 "$tmp_rule" "$NFTABLES_RULE_FILE"

if [ ! -e "$NFTABLES_CONF" ]; then
    cat > "$NFTABLES_CONF" <<EOF
#!/usr/sbin/nft -f

flush ruleset

include "$NFTABLES_RULE_FILE"
EOF
else
    backup_conf="$NFTABLES_CONF.bak-$(date +%Y%m%d%H%M%S)"
    cp -a "$NFTABLES_CONF" "$backup_conf"

    if grep -Eq "$redirect_pattern" "$NFTABLES_CONF"; then
        redirect_already_present=true
    elif grep -Eq "$conflicting_redirect_pattern" "$NFTABLES_CONF"; then
        die "conflicting tcp/$PUBLIC_PORT redirect already exists in $NFTABLES_CONF"
    elif ! grep -Fq "include \"$NFTABLES_RULE_FILE\"" "$NFTABLES_CONF" \
        && ! grep -Fq "include \"$NFTABLES_RULE_DIR/*.nft\"" "$NFTABLES_CONF"; then
        printf '\ninclude "%s"\n' "$NFTABLES_RULE_FILE" >> "$NFTABLES_CONF"
    fi
fi

if ! "$NFT" -c -f "$NFTABLES_CONF"; then
    if [ -n "$backup_conf" ]; then
        cp -a "$backup_conf" "$NFTABLES_CONF"
        echo "restored $NFTABLES_CONF from $backup_conf" >&2
    fi
    die "nftables syntax check failed"
fi

"$NFT" -f "$NFTABLES_CONF"

if command -v systemctl >/dev/null 2>&1; then
    systemctl enable --now nftables.service
fi

echo "Installed nftables redirect: tcp/$PUBLIC_PORT -> tcp/$TARGET_PORT"
echo "Rule file: $NFTABLES_RULE_FILE"
[ "$redirect_already_present" = false ] || echo "Existing redirect in $NFTABLES_CONF was already present"
[ -z "$backup_conf" ] || echo "Config backup: $backup_conf"
