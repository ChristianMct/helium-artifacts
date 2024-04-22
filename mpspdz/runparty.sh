#!/bin/bash

echo "Setting network counters"
iptables -I OUTPUT 
iptables -I INPUT


interface='eth0'
# eg. 50mbit
rate=
# eg. 10ms
delay=
if [[ ! -z "${RATE_LIMIT}" ]]; then
    rate="rate ${RATE_LIMIT}"
fi
if [[ ! -z "${DELAY}" ]]; then
    delay="delay ${DELAY}"
fi

if [[ -n "${RATE_LIMIT}" ]] || [[ -n "${DELAY}" ]]; then
    echo "Applying network condition $rate $delay"

    # apply egress traffic rate limit
    tc qdisc add dev $interface root netem $delay $rate || exit 1
fi

eval $@

#python3 check_output.py Player-Data/Output-P0-expected Output-P0-0 79873

iptables -nxvL OUTPUT
iptables -nxvL INPUT
