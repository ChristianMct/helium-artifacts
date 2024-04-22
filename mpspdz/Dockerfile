FROM mpspdz as expbase

#ARG src="matmult.mpc"
ARG compile_options="--field=15 -P 65537"
ARG program_args=

RUN --mount=type=bind,source=./Programs/Source,target=./Programs/Source ./compile.py ${compile_options} "matmult.mpc" ${program_args}

RUN apt update
RUN apt install -y iptables iproute2 iperf3

COPY ./runparty.sh ./runparty.sh

FROM expbase as exp
ARG machine="semi-party.x"

RUN cp /usr/local/bin/${machine} /usr/local/bin/party.x

RUN mkdir -p Player-Data

ENTRYPOINT [ "./runparty.sh" ]
