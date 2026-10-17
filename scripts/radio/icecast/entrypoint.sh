#!/bin/sh
# 비밀번호는 환경변수(미니PC ~/.config/nexis/radio.env)에서 받아 설정 파일에 채운다. 화면에 찍지 않는다.
set -eu
: "${ICECAST_SOURCE_PASSWORD:?}" "${ICECAST_ADMIN_PASSWORD:?}"
export ICECAST_RELAY_PASSWORD="${ICECAST_RELAY_PASSWORD:-$ICECAST_ADMIN_PASSWORD}"
export ICECAST_MAX_CLIENTS="${ICECAST_MAX_CLIENTS:-60}"
envsubst < /etc/icecast2/icecast.xml.tmpl > /tmp/icecast/icecast.xml
exec icecast2 -c /tmp/icecast/icecast.xml
