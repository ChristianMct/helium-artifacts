###############################################################################
# Build this stage for a build environment, e.g.:                             #
#                                                                             #
# docker build --tag mpspdz:buildenv --target buildenv .                      #
#                                                                             #
# The above is equivalent to:                                                 #
#                                                                             #
#   docker build --tag mpspdz:buildenv \                                      #
#     --target buildenv \                                                     #
#     --build-arg arch=native \                                               #
#     --build-arg cxx=clang++-11 \                                            #
#     --build-arg use_ntl=0 \                                                 #
#     --build-arg prep_dir="Player-Data" \                                    #
#     --build-arg ssl_dir="Player-Data"                                       #
#     --build-arg cryptoplayers=0                                             #
#                                                                             #
# To build for an x86-64 architecture, with g++, NTL (for HE), custom         #
# prep_dir & ssl_dir, and to use encrypted channels for 4 players:            #
#                                                                             #
#   docker build --tag mpspdz:buildenv \                                      #
#     --target buildenv \                                                     #
#     --build-arg arch=x86-64 \                                               #
#     --build-arg cxx=g++ \                                                   #
#     --build-arg use_ntl=1 \                                                 #
#     --build-arg prep_dir="/opt/prepdata" \                                  #
#     --build-arg ssl_dir="/opt/ssl"                                          #
#     --build-arg cryptoplayers=4 .                                           #
#                                                                             #
# To work in a container to build different machines, and compile programs:   #
#                                                                             #
# docker run --rm -it mpspdz:buildenv bash                                    #
#                                                                             #
# Once in the container, build a machine and compile a program:               #
#                                                                             #
#   $ make replicated-ring-party.x                                            #
#   $ ./compile.py -R 64 tutorial                                             #
#                                                                             #
###############################################################################
FROM python:3.10.3-bullseye as buildenv

RUN apt-get update && apt-get install -y --no-install-recommends \
                automake \
                build-essential \
                clang-11 \
		cmake \
                git \
                libboost-dev \
                libboost-thread-dev \
                libclang-dev \
                libgmp-dev \
                libntl-dev \
                libsodium-dev \
                libssl-dev \
                libtool \
                vim \
                gdb \
                valgrind \
        && rm -rf /var/lib/apt/lists/*

ENV MP_SPDZ_HOME /usr/src/MP-SPDZ
WORKDIR $MP_SPDZ_HOME

RUN pip install --upgrade pip ipython

COPY . .

ARG arch=native
ARG cxx=clang++-11
ARG use_ntl=1
ARG prep_dir="Player-Data"
ARG ssl_dir="Player-SSL"
ARG cryptoplayers=8

RUN echo "ARCH = -march=${arch}" >> CONFIG.mine \
        && echo "CXX = ${cxx}" >> CONFIG.mine \
        && echo "USE_NTL = ${use_ntl}" >> CONFIG.mine \
        && echo "MY_CFLAGS += -I/usr/local/include" >> CONFIG.mine \
        && echo "MY_CFLAGS += -DDEBUG" >> CONFIG.mine \
        && echo "MY_CFLAGS += -DDEBUG_NETWORKING" >> CONFIG.mine \
        && echo "MY_LDLIBS += -Wl,-rpath -Wl,/usr/local/lib -L/usr/local/lib" \
            >> CONFIG.mine \
        && mkdir -p $prep_dir $ssl_dir \
        && echo "PREP_DIR = '-DPREP_DIR=\"${prep_dir}/\"'" >> CONFIG.mine \
        && echo "SSL_DIR = '-DSSL_DIR=\"${ssl_dir}/\"'" >> CONFIG.mine


# ssl keys
ENV PLAYERS ${cryptoplayers}
RUN ./Scripts/setup-ssl.sh ${cryptoplayers} ${ssl_dir}

RUN make boost
RUN make -j30 libote

ARG gfp_mod_sz=1

RUN echo "MOD = -DGFP_MOD_SZ=${gfp_mod_sz}" >> CONFIG.mine

RUN make clean && make -j30 semi-party.x hemi-party.x soho-party.x temi-party.x

RUN cp -t /usr/local/bin/ semi-party.x hemi-party.x soho-party.x temi-party.x
