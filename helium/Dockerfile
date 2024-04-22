#########################################
#  Builder                              #
#########################################
FROM golang:latest as builder

ARG APP=./app

WORKDIR /helium

COPY go.mod ./
COPY go.sum ./

RUN go mod download

COPY ${APP} ./app

RUN --mount=type=cache,target=/root/.cache/go-build CGO_ENABLED=0 go build -v -o node ./app 

#########################################
#  Image                                #
#########################################
FROM ubuntu:latest

WORKDIR /helium

RUN apt update
RUN apt install -y iperf3 git iproute2

COPY ./shape_traffic_and_start.sh /helium/shape_traffic_and_start.sh

COPY --from=builder /helium/node /helium/node

EXPOSE 40000

ENTRYPOINT [ "/helium/node" ]
